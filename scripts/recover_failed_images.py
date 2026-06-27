"""Recovery script for the ~23 destinations that failed in the main run.

Two failure modes:
  1. Disambiguation / no lead image (Portland, Austin, Orlando, ...). Fix: search
     the action API with `"{name} {country}"` to disambiguate.
  2. Lead image is an SVG flag/map whose Special:FilePath render 404'd. Fix: use
     the action API's `pageimages` thumbnail URL, which renders SVGs as PNGs
     reliably (upload.wikimedia.org/.../thumb/.../800px-Foo.svg.png).

Reads `data/destinations.csv`, retries only rows whose `<id>.webp` is missing,
and uses the action API (with backoff) for both lookups. ~23 requests is well
within the rate limit even with conservative delays.
"""

from __future__ import annotations

import csv
import logging
import os
import time
from io import BytesIO

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

_WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "HolidayPlanner/1.0 (Rockborne training project; contact via repo)"
_HEADERS = {"User-Agent": _USER_AGENT}
_TIMEOUT = 15

_CSV_PATH = os.path.join("data", "destinations.csv")
_OUTPUT_DIR = os.path.join("images", "destinations")

_TARGET_WIDTH = 800
_TARGET_HEIGHT = 450
_WEBP_QUALITY = 88

_DELAY_SECONDS = 3.0  # extra-polite; only ~23 calls
_MAX_429_RETRIES = 5
_429_BACKOFFS = (5, 10, 20, 40, 60)


def _build_session() -> requests.Session:
    retry = Retry(total=3, backoff_factor=0.5,
                  status_forcelist=(500, 502, 503, 504),
                  allowed_methods=frozenset({"GET"}), raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry)
    sess = requests.Session()
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    sess.headers.update(_HEADERS)
    return sess


def _api_get(sess: requests.Session, params: dict) -> dict | None:
    for attempt in range(_MAX_429_RETRIES + 1):
        try:
            resp = sess.get(_WIKIPEDIA_API, params=params, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            logging.warning("Network error: %s", exc)
            return None
        if resp.status_code == 429 and attempt < _MAX_429_RETRIES:
            wait = int(resp.headers.get("Retry-After", _429_BACKOFFS[attempt]) or _429_BACKOFFS[attempt])
            logging.warning("429 — backing off %ds (attempt %d/%d)", wait, attempt + 1, _MAX_429_RETRIES)
            time.sleep(wait)
            continue
        if not resp.ok:
            logging.warning("HTTP %d: %s", resp.status_code, resp.text[:200])
            return None
        return resp.json()
    return None


def _resolve_thumbnail_url(sess: requests.Session, name: str, country: str) -> str | None:
    """Search with `name country` and return the pageimages thumbnail URL.

    The action API's thumbnail URL renders SVGs as PNGs at the requested width,
    which is what Special:FilePath failed to do for flag/map SVGs.
    """
    for query in (f"{name} {country}", name):
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 0,
            "gsrlimit": 1,
            "prop": "pageimages",
            "piprop": "thumbnail",
            "pithumbsize": _TARGET_WIDTH,
            "redirects": 1,
            "format": "json",
        }
        data = _api_get(sess, params)
        time.sleep(_DELAY_SECONDS)
        if not data:
            continue
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = page.get("thumbnail")
            if thumb and "source" in thumb:
                return thumb["source"]
    return None


def _crop_to_16_9(img: Image.Image) -> Image.Image:
    target = _TARGET_WIDTH / _TARGET_HEIGHT
    current = img.width / img.height
    if abs(current - target) < 0.01:
        return img
    if current > target:
        new_w = int(img.height * target)
        left = (img.width - new_w) // 2
        return img.crop((left, 0, left + new_w, img.height))
    new_h = int(img.width / target)
    top = (img.height - new_h) // 2
    return img.crop((0, top, img.width, top + new_h))


def _download_crop_save(sess: requests.Session, url: str, dest_id: str) -> None:
    for attempt in range(_MAX_429_RETRIES + 1):
        resp = sess.get(url, timeout=_TIMEOUT)
        if resp.status_code == 429 and attempt < _MAX_429_RETRIES:
            wait = int(resp.headers.get("Retry-After", _429_BACKOFFS[attempt]) or _429_BACKOFFS[attempt])
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break
    img = Image.open(BytesIO(resp.content))
    if img.mode != "RGB":
        img = img.convert("RGB")
    img = _crop_to_16_9(img)
    img = img.resize((_TARGET_WIDTH, _TARGET_HEIGHT), Image.Resampling.LANCZOS)
    out = os.path.join(_OUTPUT_DIR, f"{dest_id}.webp")
    img.save(out, "WEBP", quality=_WEBP_QUALITY)
    logging.info("Saved %s", out)


def main() -> None:
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    sess = _build_session()

    with open(_CSV_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    missing = [r for r in rows if not os.path.exists(os.path.join(_OUTPUT_DIR, f"{r['id']}.webp"))]
    logging.info("Recovering %d missing images", len(missing))

    saved, failed = 0, []
    for row in missing:
        dest_id, name, country = row["id"], row["name"], row["country"]
        try:
            url = _resolve_thumbnail_url(sess, name, country)
            if not url:
                failed.append((name, "no thumbnail via action API"))
                logging.warning("No thumbnail for %r (%s)", name, country)
                continue
            _download_crop_save(sess, url, dest_id)
            saved += 1
        except Exception as exc:
            failed.append((name, str(exc)))
            logging.warning("Failed %r: %s", name, exc)

    logging.info("Recovery done. saved=%d failed=%d", saved, len(failed))
    for name, reason in failed:
        logging.info("  - %s: %s", name, reason)


if __name__ == "__main__":
    main()
