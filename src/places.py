"""Google Places nearby venue search."""

from __future__ import annotations


def fetch_nearby_venues(lat: float, lng: float, api_key: str) -> list[dict]:
    """Fetch bars, restaurants, and nightclubs near coordinates.

    Returns:
        List of venue dicts. Each item should include:
        name, lat, lng, rating, price_level (0-4), maps_url.
    """
    raise NotImplementedError
