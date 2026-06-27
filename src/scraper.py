"""FCDO travel advice HTML scraper for the dashboard Safety tab.

Classic web scraping: fetches the human-facing GOV.UK foreign travel advice
pages with `requests` and extracts the main content with BeautifulSoup.
This is the project's web-scrape requirement (distinct from Wikivoyage,
which uses the MediaWiki API).

Two pages are fetched per country and concatenated into `safety_text`:
  1. /foreign-travel-advice/{slug}            — landing ("Warnings and insurance")
  2. /foreign-travel-advice/{slug}/safety-and-security

The slug comes from `destinations.csv` (`gov_uk_country`), the single source
of truth. UK destinations use the sentinel value "UK" and return a hardcoded
domestic safety summary (GOV.UK publishes no foreign travel advice for the UK).

All network errors are caught inside `fetch_fcdo_advice` and a shared
placeholder is returned — the caller never needs to wrap the fetch.
"""

from __future__ import annotations

import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.gov.uk/foreign-travel-advice"
_USER_AGENT = "HolidayPlanner/1.0 (Rockborne training project)"
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml",
}
_TIMEOUT = 15  # seconds — GOV.UK pages are large and CDN-served

# Sentinel value in destinations.csv `gov_uk_country` for domestic UK rows.
# GOV.UK has no foreign-travel-advice page for the UK itself.
_UK_SENTINEL = "UK"

# Shared placeholder returned when the slug is missing/invalid or when any
# network/parse error occurs. NOT an empty string — `summarise_tab` skips the
# LLM call on empty input, and we want the Safety tab to show something.
FCDO_UNAVAILABLE = (
    "FCDO travel advice is currently unavailable for this destination. "
    "Visit www.gov.uk/foreign-travel-advice for the latest official guidance."
)

# Hardcoded domestic safety summary for UK destinations — no HTTP call.
# Kept general and evergreen so it does not go stale between scrapes.
_UK_SAFETY_TEXT = (
    "Domestic travel within the United Kingdom — no FCDO foreign travel advice applies.\n\n"
    "The UK is generally a safe destination for domestic travellers. Normal precautions apply:\n"
    "- Keep an eye on personal belongings in busy tourist areas and on public transport.\n"
    "- Plan journeys in advance; rail and metro services can be disrupted by industrial action, "
    "particularly on weekends. Check operator websites before travelling.\n"
    "- Weather can change quickly, especially in upland areas (Lake District, Scottish Highlands, "
    "Snowdonia). Check the Met Office forecast and carry appropriate clothing for hikes.\n"
    "- Emergency services: dial 999 or 112 for police, ambulance, fire, coastguard, or mountain rescue.\n"
    "- NHS treatment is free at the point of use for UK residents; carry proof of entitlement if asked.\n"
    "- Stay informed via local news and official GOV.UK channels during severe weather or major events."
)


def _html_to_text(html: str) -> str:
    """Strip GOV.UK page HTML to clean plain text for LLM consumption.

    Extracts the `<main>` element (drops global nav, cookie banner, footer),
    then `get_text()` + collapse blank lines. Generic — no brittle CSS
    selectors — so minor GOV.UK layout changes don't break the scrape.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Prefer <main>; fall back to whole document if GOV.UK ever drops it.
    main = soup.find("main")
    root = main if main is not None else soup

    # Drop script/style noise that sometimes survives inside <main>.
    for tag in root.find_all(["script", "style", "nav", "aside"]):
        tag.decompose()

    text = root.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _fetch_page(slug: str, sub_page: str | None = None) -> str:
    """Fetch a single GOV.UK travel advice page and return plain text.

    Args:
        slug: GOV.UK country slug (e.g. "france", "czechia").
        sub_page: Optional sub-page segment (e.g. "safety-and-security").

    Raises:
        requests.RequestException — caught by the caller.
    """
    url = f"{_BASE_URL}/{slug}"
    if sub_page:
        url = f"{url}/{sub_page}"

    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return _html_to_text(resp.text)


def fetch_fcdo_advice(gov_uk_country: str) -> dict:
    """Scrape FCDO travel advice for a destination.

    Args:
        gov_uk_country: GOV.UK URL slug from `destinations.gov_uk_country`
            (e.g. "france", "czechia", "usa"). The sentinel value "UK"
            returns a hardcoded domestic safety summary without any HTTP call.

    Returns:
        {"safety_text": str, "entry_text": str}. `entry_text` is currently
        always empty (entry requirements not scraped in Phase 2). On any
        failure — missing slug, 404, network error, parse error — returns
        a shared placeholder constant in `safety_text`; never raises.
    """
    slug = (gov_uk_country or "").strip()

    if slug == _UK_SENTINEL:
        logger.info("FCDO: domestic UK destination — returning hardcoded safety summary.")
        return {"safety_text": _UK_SAFETY_TEXT, "entry_text": ""}

    if not slug:
        logger.warning("FCDO: empty gov_uk_country slug — returning placeholder.")
        return {"safety_text": FCDO_UNAVAILABLE, "entry_text": ""}

    try:
        landing = _fetch_page(slug)
        safety = _fetch_page(slug, sub_page="safety-and-security")

        # Concatenate with a clear separator so the LLM sees two distinct
        # sections. Either page may legitimately be short.
        parts = []
        if landing.strip():
            parts.append(f"--- FCDO landing page (warnings and insurance) ---\n\n{landing}")
        if safety.strip():
            parts.append(f"--- Safety and security ---\n\n{safety}")

        if not parts:
            logger.warning("FCDO: both pages came back empty for slug %r", slug)
            return {"safety_text": FCDO_UNAVAILABLE, "entry_text": ""}

        safety_text = "\n\n\n".join(parts)
        return {"safety_text": safety_text, "entry_text": ""}
    except Exception as exc:
        logger.warning("FCDO fetch failed for slug %r: %s", slug, exc)
        return {"safety_text": FCDO_UNAVAILABLE, "entry_text": ""}


if __name__ == "__main__":
    # Quick manual check: `python src/scraper.py <slug>`
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "france"
    result = fetch_fcdo_advice(target)
    print(f"safety_text length: {len(result['safety_text'])} chars")
    print(f"entry_text length: {len(result['entry_text'])} chars")
    print("--- First 600 chars ---")
    print(result["safety_text"][:600])
