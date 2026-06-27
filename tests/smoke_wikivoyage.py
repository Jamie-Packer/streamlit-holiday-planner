"""Smoke test for the Wikivoyage MediaWiki fetcher (no API key required).

Hits the live en.wikivoyage.org API. Run with:
    python tests/run_smoke_tests.py --wikivoyage
"""

from __future__ import annotations

from src.wikivoyage import SECTION_UNAVAILABLE, fetch_section
from tests._fixtures import WIKIVOYAGE_NEEDLE, WIKIVOYAGE_PAGE, WIKIVOYAGE_SECTION


def run() -> None:
    text = fetch_section(WIKIVOYAGE_PAGE, WIKIVOYAGE_SECTION)

    assert isinstance(text, str), "fetch_section must return a str"
    assert text.strip(), "fetch_section must return non-empty content"
    assert text != SECTION_UNAVAILABLE, (
        "expected real Wikivoyage content, got placeholder — "
        "check network or that the test destination still has the section"
    )

    lower = text.lower()
    assert "<" not in text, "expected plain text, not HTML markup"
    assert WIKIVOYAGE_NEEDLE.lower() in lower, (
        f"expected {WIKIVOYAGE_NEEDLE!r} in the Paris See section; "
        f"got: {text[:200]!r}..."
    )
    assert len(text) > 500, f"plain text too short ({len(text)} chars) — strip may be too aggressive"

    print(f"Page: {WIKIVOYAGE_PAGE!r}  Section: {WIKIVOYAGE_SECTION!r}")
    print(f"Text length: {len(text)} chars")
    print("--- First 400 chars ---")
    # ASCII-safe preview for Windows consoles that can't print wiki punctuation (e.g. ′).
    print(text[:400].encode("ascii", errors="replace").decode("ascii"))
