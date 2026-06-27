"""Smoke test for the Wikivoyage MediaWiki fetcher (no API key required).

Hits the live en.wikivoyage.org API. Run with:
    python tests/run_smoke_tests.py --wikivoyage
"""

from __future__ import annotations

from src.wikivoyage import SECTION_UNAVAILABLE, fetch_section
from tests._fixtures import WIKIVOYAGE_NEEDLE, WIKIVOYAGE_PAGE, WIKIVOYAGE_SECTION


def run() -> None:
    html = fetch_section(WIKIVOYAGE_PAGE, WIKIVOYAGE_SECTION)

    assert isinstance(html, str), "fetch_section must return a str"
    assert html.strip(), "fetch_section must return non-empty content"
    assert html != SECTION_UNAVAILABLE, (
        "expected real Wikivoyage HTML, got placeholder — "
        "check network or that the test destination still has the section"
    )

    lower = html.lower()
    assert "<" in html, "expected HTML markup in the response"
    assert WIKIVOYAGE_NEEDLE.lower() in lower, (
        f"expected {WIKIVOYAGE_NEEDLE!r} in the Paris See section; "
        f"got: {html[:200]!r}..."
    )

    print(f"Page: {WIKIVOYAGE_PAGE!r}  Section: {WIKIVOYAGE_SECTION!r}")
    print(f"HTML length: {len(html)} chars")
    print("--- First 400 chars ---")
    print(html[:400])
