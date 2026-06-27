"""Pipeline smoke: live FCDO scrape → Gemini safety-tab summary (opt-in — GEMINI_API_KEY)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from src.llm import summarise_tab
from src.scraper import FCDO_UNAVAILABLE, fetch_fcdo_advice
from tests._fixtures import (
    FCDO_SAFETY_GROUNDING_KEYWORDS,
    FCDO_SUMMARY_SLUG,
)

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"

_TAB_TYPE = "safety"


def _load_gemini_key() -> str:
    with SECRETS_PATH.open("rb") as f:
        secrets = tomllib.load(f)
    key = secrets.get("GEMINI_API_KEY")
    if not key:
        raise KeyError("GEMINI_API_KEY missing from .streamlit/secrets.toml")
    return str(key)


def run() -> None:
    result = fetch_fcdo_advice(FCDO_SUMMARY_SLUG)
    raw_text = result["safety_text"]

    assert raw_text != FCDO_UNAVAILABLE, (
        "fetch_fcdo_advice returned placeholder — check network or France GOV.UK pages"
    )
    assert len(raw_text) > 500, f"scraped safety_text too short ({len(raw_text)} chars)"

    api_key = _load_gemini_key()
    summary = summarise_tab(raw_text, _TAB_TYPE, api_key)

    assert isinstance(summary, str), "summarise_tab must return a str"
    assert summary.strip(), "summary must be non-empty"
    assert len(summary) < 1200, (
        f"summary too long ({len(summary)} chars); check prompt compliance"
    )

    lower = summary.lower()
    assert any(kw in lower for kw in FCDO_SAFETY_GROUNDING_KEYWORDS), (
        f"summary should reference scraped FCDO safety content "
        f"(one of {FCDO_SAFETY_GROUNDING_KEYWORDS!r}); got: {summary[:200]!r}..."
    )

    print(f"Slug: {FCDO_SUMMARY_SLUG!r}  Tab: {_TAB_TYPE!r}")
    print(f"Scraped text length: {len(raw_text)} chars")
    print(f"Summary length: {len(summary)} chars")
    print("--- Summary ---")
    print(summary.encode("ascii", errors="replace").decode("ascii"))
