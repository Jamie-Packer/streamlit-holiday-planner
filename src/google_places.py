"""Google Places API (New) fetching for the dashboard map tab.

Queries nearby cafes, bars, attractions, or nightclubs around a destination's
lat/lng using the modern Google Places API (New).

The API key is passed in from the UI layer (`st.secrets["GOOGLE_PLACES_API_KEY"]`).
This module contains NO Streamlit imports, keeping it fully testable outside of Streamlit.
"""

from __future__ import annotations

import logging
import requests

logger = logging.getLogger(__name__)

_URL = "https://places.googleapis.com/v1/places:searchNearby"
_TIMEOUT = 10  # seconds

# Mapping view tab keys to Google Places API (New) standard Table-A types.
# The API is strict about type names — an unknown value yields HTTP 400, so
# these must match Google's documented Place Types (New) exactly. Note
# `night_club` (underscore); the un-underscored `nightclub` is NOT a valid
# type and was the cause of the nightclub tab's 400 errors.
_CATEGORY_TO_TYPES: dict[str, list[str]] = {
    "cafes": ["cafe", "coffee_shop"],
    "bars": ["bar", "pub"],
    "attractions": ["tourist_attraction"],
    "nightclub": ["night_club"],
}


def fetch_google_places(lat: float, lng: float, category: str, api_key: str) -> list[dict]:
    """Fetch nearby venues of a specific category from Google Places API (New).

    Args:
        lat: Latitude of the destination.
        lng: Longitude of the destination.
        category: One of 'cafes', 'bars', 'attractions', 'nightclub'.
        api_key: Google Places API key (passed in from secrets).

    Returns:
        List of venue dicts, each with keys:
        {"name": str, "lat": float, "lng": float, "google_maps_uri": str,
         "address": str, "primary_type": str, "business_status": str,
         "wheelchair_accessible": bool}
        Returns an empty list on any error.
    """
    category_key = category.lower().strip()
    included_types = _CATEGORY_TO_TYPES.get(category_key)
    if not included_types:
        logger.warning("Unknown Google Places category requested: %s", category)
        return []

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # Field mask kept inside the Nearby Search **Pro** SKU tier
        # (5,000 free monthly calls vs only 1,000 for Enterprise). We dropped
        # `rating` + `priceLevel` (Enterprise SKU) — on Streamlit Community
        # Cloud a cold start wipes the runtime cache, so every un-seeded
        # destination re-hits the API; staying on Pro protects the monthly
        # quota. Pro-tier additions used by the dashboard:
        #   - shortFormattedAddress       (compact tooltip address)
        #   - primaryTypeDisplayName      (friendly "Espresso bar" vs "cafe")
        #   - businessStatus              (skip CLOSED_PERMANENTLY on render)
        #   - accessibilityOptions        (♿ badge in popup)
        "X-Goog-FieldMask": (
            "places.displayName,places.location,places.googleMapsUri,"
            "places.shortFormattedAddress,places.primaryTypeDisplayName,"
            "places.businessStatus,places.accessibilityOptions"
        ),
    }

    payload = {
        "includedTypes": included_types,
        "maxResultCount": 15,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lng,
                },
                "radius": 1500.0,  # 1.5 km radius to catch a reasonable selection of venues
            }
        }
    }

    try:
        response = requests.post(_URL, json=payload, headers=headers, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning(
            "Google Places fetch failed for category %s at (%s, %s): %s",
            category,
            lat,
            lng,
            exc,
        )
        return []

    venues: list[dict] = []
    for place in data.get("places", []):
        location = place.get("location", {})
        display_name = place.get("displayName", {})
        type_display_name = place.get("primaryTypeDisplayName", {})
        accessibility = place.get("accessibilityOptions", {})

        venues.append({
            "name": display_name.get("text", "Unknown"),
            "lat": location.get("latitude"),
            "lng": location.get("longitude"),
            "google_maps_uri": place.get("googleMapsUri", ""),
            "address": place.get("shortFormattedAddress", "No address available"),
            "primary_type": type_display_name.get("text", "Unknown"),
            "business_status": place.get("businessStatus", "OPERATIONAL"),
            "wheelchair_accessible": bool(accessibility.get("wheelchairAccessibleEntrance", False)),
        })

    return venues
