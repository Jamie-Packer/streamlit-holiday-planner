"""Wikivoyage MediaWiki API client for See / Do / Drink sections.

Two-step flow per fetch:
  1. search: resolve `destinations.name` to the best Wikivoyage article title
     (handles minor spelling/variant mismatches in our CSV).
  2. parse: fetch the requested section's HTML for that title, then strip to
     plain text before returning so the LLM receives a compact, token-efficient
     payload rather than raw wiki markup.

Results are cached in the DuckDB `wikivoyage` table by `database.py`
orchestrators, so repeat dashboard visits cost zero API calls.

Wikivoyage is a separate wiki from Wikipedia; hardcoding the API URL below
guarantees we never pull Wikipedia content.
"""

from __future__ import annotations

import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_API_URL = "https://en.wikivoyage.org/w/api.php"
_USER_AGENT = "HolidayPlanner/1.0 (Rockborne training project)"
_HEADERS = {"User-Agent": _USER_AGENT}
_TIMEOUT = 10  # seconds

_VALID_SECTIONS = frozenset({"See", "Do", "Drink"})

# Shared placeholder returned when the article or section is missing, or when
# the API call fails. NOT an empty string — `summarise_tab` skips the LLM call
# on empty input, and we want the dashboard tab to show something meaningful.
SECTION_UNAVAILABLE = (
    "No Wikivoyage content available for this section yet. "
    "Try refreshing, or check the destination on wikivoyage.org."
)


def _search_title(name: str) -> str | None:
    """Resolve a destination name to the best Wikivoyage article title.

    Returns the top hit's title, or None if no match. Uses the MediaWiki
    search list so minor spelling/variant mismatches in our CSV are tolerated.
    """
    params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srnamespace": 0,  # main namespace only — no User:/Talk: pages
        "srlimit": 1,
        "format": "json",
    }
    resp = requests.get(_API_URL, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    hits = data.get("query", {}).get("search", [])
    if not hits:
        return None
    return hits[0].get("title")


def _find_section_index(title: str, section: str) -> int | None:
    """Return the MediaWiki section index for `section` on page `title`.

    Wikivoyage sections are addressed by integer index in the parse API, so we
    fetch the section list and look up the matching name.
    """
    params = {
        "action": "parse",
        "page": title,
        "prop": "sections",
        "redirects": 1,  # follow #REDIRECT pages to their target
        "format": "json",
    }
    resp = requests.get(_API_URL, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        # e.g. missing page — caller will surface as placeholder
        logger.warning("Wikivoyage sections list error for %r: %s", title, data["error"])
        return None
    sections = data.get("parse", {}).get("sections", [])
    for s in sections:
        # Normalise for comparison — strip whitespace and lowercase.
        if s.get("line", "").strip().lower() == section.lower():
            return int(s["index"])
    return None


def _fetch_section_html(title: str, section_index: int) -> str:
    """Fetch rendered HTML for one section of a Wikivoyage page."""
    params = {
        "action": "parse",
        "page": title,
        "section": section_index,
        "prop": "text",
        "redirects": 1,
        "format": "json",
    }
    resp = requests.get(_API_URL, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        logger.warning("Wikivoyage parse error for %r section %d: %s",
                       title, section_index, data["error"])
        return ""
    html = data.get("parse", {}).get("text", {}).get("*", "")
    return html or ""


def _html_to_text(html: str) -> str:
    """Strip wiki HTML to clean plain text for LLM consumption.

    Removes edit links, coordinate spans, and collapses whitespace so the
    result is compact and token-efficient without losing descriptive content.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Drop edit links and coordinate/map elements — pure wiki chrome.
    for tag in soup.find_all(class_=re.compile(r"mw-editsection|geo|coordinates|noprint")):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Collapse runs of blank lines and strip leading/trailing whitespace.
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def fetch_section(page_title: str, section: str) -> str:
    """Fetch HTML for a Wikivoyage article section.

    Args:
        page_title: Destination name (from `destinations.name`). Resolved to the
            best Wikivoyage article title via the search API, so minor CSV/name
            mismatches are tolerated.
        section: One of "See", "Do", or "Drink".

    Returns:
        Section content as plain text, ready to pass to `summarise_tab`. Returns a
        shared placeholder constant if the article or section is missing, or if
        any network/API error occurs — never raises.
    """
    if section not in _VALID_SECTIONS:
        raise ValueError(
            f"section must be one of {sorted(_VALID_SECTIONS)!r}, got {section!r}"
        )

    try:
        title = _search_title(page_title)
        if not title:
            logger.warning("Wikivoyage search returned no results for %r", page_title)
            return SECTION_UNAVAILABLE

        idx = _find_section_index(title, section)
        if idx is None:
            logger.info("Wikivoyage page %r has no %r section", title, section)
            return SECTION_UNAVAILABLE

        html = _fetch_section_html(title, idx)
        if not html or not html.strip():
            logger.info("Wikivoyage section %r on %r came back empty", section, title)
            return SECTION_UNAVAILABLE
        return _html_to_text(html)
    except Exception as exc:
        logger.warning("Wikivoyage fetch_section failed for %r/%r: %s",
                       page_title, section, exc)
        return SECTION_UNAVAILABLE
