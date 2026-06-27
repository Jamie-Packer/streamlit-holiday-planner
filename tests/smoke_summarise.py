"""Smoke test for Gemini tab summarisation (opt-in — uses GEMINI_API_KEY)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from src.llm import summarise_tab
from tests._fixtures import KRAKOW_SEE_RAW, SUMMARISE_TAB_TYPE

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"

_GROUNDING_KEYWORDS = ("wawel", "market", "kazimierz")


def _load_gemini_key() -> str:
    with SECRETS_PATH.open("rb") as f:
        secrets = tomllib.load(f)
    key = secrets.get("GEMINI_API_KEY")
    if not key:
        raise KeyError("GEMINI_API_KEY missing from .streamlit/secrets.toml")
    return str(key)


def run() -> None:
    api_key = _load_gemini_key()
    summary = summarise_tab(KRAKOW_SEE_RAW, SUMMARISE_TAB_TYPE, api_key)

    assert isinstance(summary, str), "summarise_tab must return a str"
    assert summary.strip(), "summary must be non-empty"
    assert len(summary) < 800, f"summary too long ({len(summary)} chars; target ~80–120 words)"

    lower = summary.lower()
    assert any(kw in lower for kw in _GROUNDING_KEYWORDS), (
        f"summary should reference fixture content; got: {summary[:200]!r}..."
    )

    print(f"Tab type: {SUMMARISE_TAB_TYPE!r}")
    print(f"Input length: {len(KRAKOW_SEE_RAW)} chars")
    print(f"Summary length: {len(summary)} chars")
    print("--- Summary ---")
    print(summary)
