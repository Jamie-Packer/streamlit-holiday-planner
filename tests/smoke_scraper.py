"""Smoke test for the FCDO GOV.UK travel advice scraper (no API key required).

Hits the live www.gov.uk site. Run with:
    python tests/run_smoke_tests.py --scraper
"""

from __future__ import annotations

from src.scraper import FCDO_UNAVAILABLE, fetch_fcdo_advice
from tests._fixtures import FCDO_NEEDLE, FCDO_SLUG


def run() -> None:
    # Live scrape of a real country page.
    result = fetch_fcdo_advice(FCDO_SLUG)

    assert isinstance(result, dict), "fetch_fcdo_advice must return a dict"
    assert "safety_text" in result and "entry_text" in result, (
        "result must have safety_text and entry_text keys"
    )

    text = result["safety_text"]
    assert isinstance(text, str), "safety_text must be a str"
    assert text.strip(), "safety_text must be non-empty"
    assert text != FCDO_UNAVAILABLE, (
        "expected real FCDO content, got placeholder — "
        "check network or that GOV.UK still serves the test slug"
    )
    assert "<" not in text[:2000], "expected plain text, not HTML markup (in first 2k chars)"
    assert FCDO_NEEDLE.lower() in text.lower(), (
        f"expected {FCDO_NEEDLE!r} in scraped content; got: {text[:200]!r}..."
    )
    assert len(text) > 500, f"safety_text too short ({len(text)} chars) — strip may be too aggressive"

    # UK sentinel branch — no HTTP, must return the hardcoded domestic summary.
    uk_result = fetch_fcdo_advice("UK")
    assert uk_result["safety_text"] != FCDO_UNAVAILABLE, (
        "UK sentinel must return the domestic safety summary, not the placeholder"
    )
    assert "United Kingdom" in uk_result["safety_text"]

    # Empty slug branch — must return placeholder, never raise.
    empty_result = fetch_fcdo_advice("")
    assert empty_result["safety_text"] == FCDO_UNAVAILABLE, (
        "empty slug must return the placeholder constant"
    )

    print(f"Slug: {FCDO_SLUG!r}")
    print(f"safety_text length: {len(text)} chars")
    print(f"entry_text length: {len(result['entry_text'])} chars")
    print("--- First 400 chars ---")
    print(text[:400].encode("ascii", errors="replace").decode("ascii"))
