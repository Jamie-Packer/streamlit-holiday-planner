"""Open-Meteo weather and climate fetching."""

from __future__ import annotations


def fetch_forecast(lat: float, lng: float) -> dict:
    """Fetch current and 7-day forecast from Open-Meteo.

    Returns an Open-Meteo forecast payload dict. Expected keys include
    daily time, temperature, and precipitation series under nested objects
    such as "daily" and "current".
    """
    raise NotImplementedError


def fetch_climate(lat: float, lng: float) -> dict:
    """Fetch historical monthly climate averages from Open-Meteo.

    Returns an Open-Meteo climate payload dict with monthly temperature
    and precipitation series suitable for seasonal charts.
    """
    raise NotImplementedError
