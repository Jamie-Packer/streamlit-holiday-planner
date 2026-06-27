"""Smoke test for Open-Meteo weather fetchers."""

from __future__ import annotations

import pandas as pd

from src.weather import fetch_climate, fetch_forecast
from tests._fixtures import PARIS_LAT, PARIS_LNG


def run() -> None:
    forecast = fetch_forecast(PARIS_LAT, PARIS_LNG)
    assert isinstance(forecast, dict), "fetch_forecast must return a dict"
    for key in ("current", "daily", "latitude", "longitude"):
        assert key in forecast, f"fetch_forecast missing key: {key}"

    current = forecast["current"]
    assert isinstance(current, dict), "current must be a dict"
    for key in ("temperature", "humidity", "cloud_cover", "wind_speed"):
        assert key in current, f"current missing key: {key}"

    daily = forecast["daily"]
    assert isinstance(daily, pd.DataFrame), "daily must be a DataFrame"
    assert not daily.empty, "daily forecast must not be empty"

    climate = fetch_climate(PARIS_LAT, PARIS_LNG)
    assert isinstance(climate, pd.DataFrame), "fetch_climate must return a DataFrame"
    assert not climate.empty, "climate DataFrame must not be empty"
    for col in ("date", "temperature_mean", "precipitation"):
        assert col in climate.columns, f"climate missing column: {col}"
