"""Smoke test for Geoapify venue fetcher."""

from __future__ import annotations

from src.places import fetch_venues
from tests._fixtures import PARIS_LAT, PARIS_LNG

_VENUE_KEYS = ("name", "category", "lat", "lng")


def run() -> None:
    venues = fetch_venues(PARIS_LAT, PARIS_LNG)
    assert isinstance(venues, list), "fetch_venues must return a list"
    assert len(venues) > 0, "Paris should return at least one venue"

    for venue in venues:
        assert isinstance(venue, dict), "each venue must be a dict"
        for key in _VENUE_KEYS:
            assert key in venue, f"venue missing key: {key}"
