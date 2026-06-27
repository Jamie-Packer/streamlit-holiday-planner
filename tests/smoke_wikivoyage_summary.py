"""Pipeline smoke: live Wikivoyage fetch → Gemini tab summary (opt-in — GEMINI_API_KEY)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from src.llm import summarise_tab
from src.wikivoyage import SECTION_UNAVAILABLE, fetch_section
from tests._fixtures import WIKIVOYAGE_NEEDLE, WIKIVOYAGE_PAGE, WIKIVOYAGE_SECTION

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"

_TAB_TYPE = "see"


def _load_gemini_key() -> str:
    with SECRETS_PATH.open("rb") as f:
        secrets = tomllib.load(f)
    key = secrets.get("GEMINI_API_KEY")
    if not key:
        raise KeyError("GEMINI_API_KEY missing from .streamlit/secrets.toml")
    return str(key)


def run() -> None:
    raw_text = fetch_section(WIKIVOYAGE_PAGE, WIKIVOYAGE_SECTION)
    assert raw_text != SECTION_UNAVAILABLE, (
        "fetch_section returned placeholder — check network or Paris See section"
    )
    assert WIKIVOYAGE_NEEDLE.lower() in raw_text.lower(), (
        f"expected {WIKIVOYAGE_NEEDLE!r} in fetched text before summarisation"
    )

    api_key = _load_gemini_key()
    summary = summarise_tab(raw_text, _TAB_TYPE, api_key)

    assert isinstance(summary, str), "summarise_tab must return a str"
    assert summary.strip(), "summary must be non-empty"
    assert len(summary) < 1200, (
        f"summary too long ({len(summary)} chars); check prompt compliance"
    )

    lower = summary.lower()
    assert WIKIVOYAGE_NEEDLE.lower() in lower, (
        f"summary should reference fetched content ({WIKIVOYAGE_NEEDLE!r}); "
        f"got: {summary[:200]!r}..."
    )

    print(f"Page: {WIKIVOYAGE_PAGE!r}  Section: {WIKIVOYAGE_SECTION!r}  Tab: {_TAB_TYPE!r}")
    print(f"Fetched text length: {len(raw_text)} chars")
    print(f"Summary length: {len(summary)} chars")
    print("--- Summary ---")
    print(summary.encode("ascii", errors="replace").decode("ascii"))
