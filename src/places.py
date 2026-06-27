"""Geoapify venue fetching for the dashboard map tab.

Fetches nearby restaurants, pubs, and cafés around a destination's lat/lng
using the Geoapify Places API. The API key is passed in from the UI layer
(`st.secrets["GEOAPIFY_API_KEY"]`) — never read at module import time, so the
module stays testable outside a Streamlit runtime (per the architecture rule:
no Streamlit imports in `src/`).
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

_URL = "https://api.geoapify.com/v2/places"
_TIMEOUT = 10  # seconds


def fetch_venues(lat: float, lng: float, api_key: str) -> list[dict]:
    """Fetch nearby restaurants, pubs, and cafés from Geoapify.

    Args:
        lat: Latitude of the destination.
        lng: Longitude of the destination.
        api_key: Geoapify API key (passed in from `st.secrets` by the caller).

    Returns:
        List of venue dicts, each with keys:
        {"name": str, "category": str, "lat": float, "lng": float}.
        Returns an empty list on any network/API error — never raises.
    """
    params = {
        "categories": "catering.restaurant,catering.pub,catering.cafe",
        "filter": f"circle:{lng},{lat},500",  # 500m radius
        "limit": 20,
        "apiKey": api_key,
    }

    try:
        response = requests.get(_URL, params=params, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("Geoapify fetch_venues failed for (%s, %s): %s", lat, lng, exc)
        return []

    venues: list[dict] = []
    for place in data.get("features", []):
        properties = place.get("properties", {})

        categories = properties.get("categories", [])
        venue_type = "Unknown"
        for category in categories:
            if category.startswith("catering."):
                venue_type = category.replace("catering.", "")
                break

        venues.append({
            "name": properties.get("name", "Unknown"),
            "category": venue_type,
            "lat": properties.get("lat"),
            "lng": properties.get("lon"),
        })

    return venues
