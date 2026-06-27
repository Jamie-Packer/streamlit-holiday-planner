"""Smoke test for Geoapify venue fetcher (opt-in — uses GEOAPIFY_API_KEY)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from src.places import fetch_venues
from tests._fixtures import PARIS_LAT, PARIS_LNG

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"

_VENUE_KEYS = ("name", "category", "lat", "lng")


def _load_geoapify_key() -> str:
    with SECRETS_PATH.open("rb") as f:
        secrets = tomllib.load(f)
    key = secrets.get("GEOAPIFY_API_KEY")
    if not key:
        raise KeyError("GEOAPIFY_API_KEY missing from .streamlit/secrets.toml")
    return str(key)


def run() -> None:
    api_key = _load_geoapify_key()
    venues = fetch_venues(PARIS_LAT, PARIS_LNG, api_key)
    assert isinstance(venues, list), "fetch_venues must return a list"
    assert len(venues) > 0, "Paris should return at least one venue"

    for venue in venues:
        assert isinstance(venue, dict), "each venue must be a dict"
        for key in _VENUE_KEYS:
            assert key in venue, f"venue missing key: {key}"
