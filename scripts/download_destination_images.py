"""One-off dev script: fetch a representative image per destination.

For each row in `data/destinations.csv`:
  1. Resolve the destination name to a Wikipedia article + lead image. Primary
     path is the REST `/page/summary/<name>` endpoint (one call, follows
     redirects, friendlier rate limits); falls back to the action API's
     `generator=search` for names that don't resolve directly.
  2. Download the lead image, center-crop to 16:9, resize to 800x450, and save
     as WebP (quality 88 — small files, no visible blur).

Output: `images/destinations/<id>.webp`. Streamlit reads these straight off
disk for instant display when the LLM returns its 3 suggestions.

This script is run locally only — Pillow is a dev dependency and is NOT in
`requirements.txt`. Re-running is safe: existing files are skipped so you can
interrupt and resume. A short delay between requests keeps Wikimedia happy.
"""

from __future__ import annotations

import csv
import logging
import os
import re
import time
from io import BytesIO
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

_WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_WIKIPEDIA_REST_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
_USER_AGENT = "HolidayPlanner/1.0 (Rockborne training project; contact via repo)"
_HEADERS = {"User-Agent": _USER_AGENT}
_TIMEOUT = 15  # seconds per request

_CSV_PATH = os.path.join("data", "destinations.csv")
_OUTPUT_DIR = os.path.join("images", "destinations")

# Output geometry — 16:9, wide enough to look crisp in a Streamlit card.
_TARGET_WIDTH = 800
_TARGET_HEIGHT = 450
_WEBP_QUALITY = 88

# Polite delay between Wikipedia API hits so we don't hammer the endpoint.
# Wikimedia's free API throttles bursts aggressively; 2s keeps us under the limit.
_DELAY_SECONDS = 2.0

# On a 429 we back off hard, honoring Retry-After if provided.
_MAX_429_RETRIES = 5
_429_DEFAULT_BACKOFFS = (5, 10, 20, 40, 60)  # seconds


def _build_session() -> requests.Session:
    """A session that retries transient network/5xx errors automatically.

    429 is handled manually in `_wiki_get` so we can honor Retry-After.
    """
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    sess = requests.Session()
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    sess.headers.update(_HEADERS)
    return sess


def _wiki_get(sess: requests.Session, params: dict) -> dict | None:
    """GET the Wikipedia action API, retrying 429s with backoff. Returns JSON or None."""
    for attempt in range(_MAX_429_RETRIES + 1):
        try:
            resp = sess.get(_WIKIPEDIA_API, params=params, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            logging.warning("Network error on %s: %s", params.get("srsearch") or params.get("titles"), exc)
            return None

        if resp.status_code == 429 and attempt < _MAX_429_RETRIES:
            retry_after = resp.headers.get("Retry-After")
            try:
                wait = int(retry_after) if retry_after else _429_DEFAULT_BACKOFFS[attempt]
            except ValueError:
                wait = _429_DEFAULT_BACKOFFS[attempt]
            logging.warning(
                "429 Too Many Requests on %s — backing off %ds (attempt %d/%d)",
                params.get("srsearch") or params.get("titles"), wait, attempt + 1, _MAX_429_RETRIES,
            )
            time.sleep(wait)
            continue

        if not resp.ok:
            logging.warning(
                "HTTP %d on %s: %s",
                resp.status_code, params.get("srsearch") or params.get("titles"), resp.text[:200],
            )
            return None

        return resp.json()

    logging.error("Exhausted 429 retries for %s", params.get("srsearch") or params.get("titles"))
    return None


def _rest_get(sess: requests.Session, url: str) -> requests.Response | None:
    """GET a Wikimedia REST endpoint, retrying 429s with backoff. Returns response or None."""
    for attempt in range(_MAX_429_RETRIES + 1):
        try:
            resp = sess.get(url, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            logging.warning("Network error on %s: %s", url, exc)
            return None

        if resp.status_code == 429 and attempt < _MAX_429_RETRIES:
            retry_after = resp.headers.get("Retry-After")
            try:
                wait = int(retry_after) if retry_after else _429_DEFAULT_BACKOFFS[attempt]
            except (ValueError, TypeError):
                wait = _429_DEFAULT_BACKOFFS[attempt]
            logging.warning("429 on %s — backing off %ds (attempt %d/%d)",
                            url, wait, attempt + 1, _MAX_429_RETRIES)
            time.sleep(wait)
            continue

        return resp

    logging.error("Exhausted 429 retries for %s", url)
    return None


_FILEPATH_ENDPOINT = "https://en.wikipedia.org/wiki/Special:FilePath/"


def _to_thumb_url(url: str, width: int = _TARGET_WIDTH) -> str:
    """Build a sized-thumbnail URL for a Wikimedia image.

    `Special:FilePath/<filename>?width=N` is a Wikimedia redirect endpoint that
    serves a correctly-sized thumbnail for any uploaded file. It's far simpler
    than constructing the `upload.wikimedia.org/.../thumb/...` path by hand
    (which differs per file type and hashing), and it's served via a CDN that
    doesn't rate-limit like the action API.

    Accepts either a raw original URL or an existing thumbnail URL — we only
    need the filename, which is the last path segment (stripped of any
    `NNNpx-` thumbnail prefix).
    """
    # Take the last path segment of the URL.
    last = url.rsplit("/", 1)[-1]
    # If it's a thumbnail (e.g. "3840px-Foo.jpg"), strip the `NNNpx-` prefix.
    last = re.sub(r"^\d+px-", "", last)
    return f"{_FILEPATH_ENDPOINT}{last}?width={width}"


def _resolve_image_url(sess: requests.Session, name: str) -> tuple[str | None, str | None]:
    """Resolve a destination name to (article_title, lead_image_url).

    Primary path: the REST summary endpoint at `/page/summary/<name>` — it
    follows redirects and returns the lead image in a single call, with friendlier
    rate limits than the action API. Falls back to `generator=search` on the
    action API for names that don't resolve directly (e.g. ambiguous place names).
    """
    from urllib.parse import quote

    rest_url = _WIKIPEDIA_REST_SUMMARY + quote(name, safe="")
    resp = _rest_get(sess, rest_url)
    if resp is not None and resp.ok:
        data = resp.json()
        title = data.get("title")
        img = data.get("originalimage") or data.get("thumbnail")
        if img and "source" in img:
            # Convert the original/thumbnail URL to a CDN thumbnail URL — the
            # CDN doesn't rate-limit like the action API and the file is far
            # smaller, so downloads are fast and reliable.
            return title, _to_thumb_url(img["source"])

    # Fallback: action API with generator=search (handles ambiguous names).
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": name,
        "gsrnamespace": 0,
        "gsrlimit": 1,
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": _TARGET_WIDTH,
        "redirects": 1,
        "format": "json",
    }
    data = _wiki_get(sess, params)
    if not data:
        return None, None
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        title = page.get("title")
        thumb = page.get("thumbnail")
        img_url = thumb["source"] if thumb and "source" in thumb else None
        return title, img_url
    return None, None


def _crop_to_16_9(img: Image.Image) -> Image.Image:
    """Center-crop an image to a 16:9 aspect ratio."""
    target_ratio = _TARGET_WIDTH / _TARGET_HEIGHT
    current_ratio = img.width / img.height

    if abs(current_ratio - target_ratio) < 0.01:
        return img

    if current_ratio > target_ratio:
        # Too wide — crop the sides.
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        return img.crop((left, 0, left + new_width, img.height))
    else:
        # Too tall — crop top and bottom.
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        return img.crop((0, top, img.width, top + new_height))


def _download_crop_and_save(sess: requests.Session, url: str, dest_id: str) -> None:
    """Download an image, crop to 16:9, resize, and save as WebP.

    Image downloads go to upload.wikimedia.org which is more lenient than the
    API, but we still back off briefly on a 429 to be safe.
    """
    for attempt in range(_MAX_429_RETRIES + 1):
        resp = sess.get(url, timeout=_TIMEOUT)
        if resp.status_code == 429 and attempt < _MAX_429_RETRIES:
            retry_after = resp.headers.get("Retry-After")
            try:
                wait = int(retry_after) if retry_after else _429_DEFAULT_BACKOFFS[attempt]
            except (ValueError, TypeError):
                wait = _429_DEFAULT_BACKOFFS[attempt]
            logging.warning("429 on image download for id=%s — backing off %ds", dest_id, wait)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break

    img = Image.open(BytesIO(resp.content))

    # WebP doesn't support paletted/transparent modes well — flatten to RGB.
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img = _crop_to_16_9(img)
    img = img.resize((_TARGET_WIDTH, _TARGET_HEIGHT), Image.Resampling.LANCZOS)

    out_path = os.path.join(_OUTPUT_DIR, f"{dest_id}.webp")
    img.save(out_path, "WEBP", quality=_WEBP_QUALITY)
    logging.info("Saved %s (%dx%d)", out_path, _TARGET_WIDTH, _TARGET_HEIGHT)


def main() -> None:
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    sess = _build_session()

    with open(_CSV_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    successes = 0
    skipped = 0
    failures: list[tuple[str, str]] = []  # (name, reason)

    for row in rows:
        dest_id = row["id"]
        name = row["name"]

        out_path = os.path.join(_OUTPUT_DIR, f"{dest_id}.webp")
        if os.path.exists(out_path):
            skipped += 1
            logging.info("Skip %s (id=%s) — already exists", name, dest_id)
            continue

        try:
            title, img_url = _resolve_image_url(sess, name)
            time.sleep(_DELAY_SECONDS)
            if not title:
                failures.append((name, "no Wikipedia article"))
                logging.warning("No Wikipedia article for %r", name)
                continue
            if not img_url:
                failures.append((name, f"no lead image on {title}"))
                logging.warning("No lead image for %r (%s)", name, title)
                continue

            _download_crop_and_save(sess, img_url, dest_id)
            successes += 1
            # No delay after image download — upload.wikimedia.org is a CDN and
            # doesn't rate-limit like the action API. The API delay above is enough.
        except Exception as exc:
            failures.append((name, str(exc)))
            logging.warning("Failed %r: %s", name, exc)

    logging.info(
        "Done. saved=%d skipped=%d failed=%d total=%d",
        successes, skipped, len(failures), len(rows),
    )
    if failures:
        logging.info("Failures:")
        for name, reason in failures:
            logging.info("  - %s: %s", name, reason)


if __name__ == "__main__":
    main()
