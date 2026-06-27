"""Smoke test for Momondo flight price scraper (opt-in — slow, needs Chrome)."""

from __future__ import annotations

from src.flights import fetch_flightprice
from tests._fixtures import FLIGHT_DATE, FLIGHT_FROM, FLIGHT_TO


def run() -> None:
    result = fetch_flightprice(FLIGHT_FROM, FLIGHT_TO, FLIGHT_DATE)
    assert isinstance(result, dict), "fetch_flightprice must return a dict"
    for key in ("price", "duration"):
        assert key in result, f"result missing key: {key}"
        assert isinstance(result[key], str) and result[key].strip(), f"{key} must be a non-empty string"
