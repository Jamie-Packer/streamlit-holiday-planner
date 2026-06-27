"""Smoke test for Gemini destination routing (opt-in — uses GEMINI_API_KEY)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from src.database import get_all_destinations
from src.llm import route_destinations
from tests._fixtures import LLM_PROMPT

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"


def _load_gemini_key() -> str:
    with SECRETS_PATH.open("rb") as f:
        secrets = tomllib.load(f)
    key = secrets.get("GEMINI_API_KEY")
    if not key:
        raise KeyError("GEMINI_API_KEY missing from .streamlit/secrets.toml")
    return str(key)


def _routing_destinations() -> list[dict]:
    """Destination rows for routing — lat/lng excluded per llm.py contract."""
    return [
        {k: v for k, v in row.items() if k not in ("lat", "lng")}
        for row in get_all_destinations()
    ]


def run() -> None:
    api_key = _load_gemini_key()
    destinations = _routing_destinations()
    valid_ids = {int(r["id"]) for r in destinations}

    assert len(valid_ids) == 300, f"expected 300 destinations, got {len(valid_ids)}"

    result = route_destinations(LLM_PROMPT, destinations, api_key)

    assert isinstance(result, list), "route_destinations must return a list"
    assert len(result) == 3, f"expected 3 IDs, got {len(result)}: {result}"
    assert len(set(result)) == 3, f"IDs must be distinct: {result}"
    for dest_id in result:
        assert isinstance(dest_id, int), f"each ID must be int, got {type(dest_id)}: {dest_id}"
        assert dest_id in valid_ids, f"ID {dest_id} not in destinations catalogue"

    print(f"Prompt: {LLM_PROMPT!r}")
    print(f"Suggested destination IDs: {result}")
