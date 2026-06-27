"""Smoke test for all database.py get_or_fetch_* orchestrators (destination id 123).

Live integration test — hits Open-Meteo, Geoapify, Wikivoyage, GOV.UK, and Gemini
on cache miss. Requires GEOAPIFY_API_KEY and GEMINI_API_KEY in secrets.toml.

Run:  python tests/run_smoke_tests.py --orchestrators
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from src import database as db

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"

DEST_ID = 123  # Klaipeda, Lithuania — gov_uk_country=lithuania


def _load_secrets() -> tuple[str, str]:
    with SECRETS_PATH.open("rb") as f:
        secrets = tomllib.load(f)
    geo = secrets.get("GEOAPIFY_API_KEY")
    gemini = secrets.get("GEMINI_API_KEY")
    if not geo:
        raise KeyError("GEOAPIFY_API_KEY missing from .streamlit/secrets.toml")
    if not gemini:
        raise KeyError("GEMINI_API_KEY missing from .streamlit/secrets.toml")
    return str(geo), str(gemini)


def _assert_cache_hit(fn, label: str) -> None:
    """Call fn twice; second result must match first (cached round-trip)."""
    first = fn()
    second = fn()
    assert first == second, f"{label}: cache hit should return identical data"


def run() -> None:
    geo_key, gemini_key = _load_secrets()

    db.init_db()
    dest = db.get_destination(DEST_ID)
    assert dest is not None, f"destination {DEST_ID} not found in planner.db"
    print(f"Destination {DEST_ID}: {dest['name']}, {dest['country']} (gov_uk_country={dest['gov_uk_country']!r})")
    print()

    # --- get_or_fetch_weather ------------------------------------------------
    weather = db.get_or_fetch_weather(DEST_ID)
    assert isinstance(weather, dict), "weather must be a dict"
    assert "forecast" in weather and "climate" in weather
    forecast = weather["forecast"]
    climate = weather["climate"]
    assert isinstance(forecast, dict), "forecast must be a dict"
    assert "current" in forecast and "daily" in forecast
    assert isinstance(forecast["daily"], list), "forecast.daily must be a list of records"
    assert len(forecast["daily"]) >= 1, "forecast should have at least one daily row"
    assert isinstance(climate, list), "climate must be a list of records"
    assert len(climate) >= 1, "climate should have at least one row"
    _assert_cache_hit(lambda: db.get_or_fetch_weather(DEST_ID), "weather")
    print(f"weather       PASS - forecast daily rows={len(forecast['daily'])}, climate rows={len(climate)}")

    # --- get_or_fetch_places -------------------------------------------------
    places = db.get_or_fetch_places(DEST_ID, geo_key)
    assert isinstance(places, list), "places must be a list"
    if places:
        for venue in places[:3]:
            assert isinstance(venue, dict)
            for key in ("name", "category", "lat", "lng"):
                assert key in venue, f"venue missing {key!r}"
    _assert_cache_hit(lambda: db.get_or_fetch_places(DEST_ID, geo_key), "places")
    print(f"places        PASS - {len(places)} venues")

    # --- get_or_fetch_wikivoyage ---------------------------------------------
    for section in ("See", "Do", "Drink"):
        text = db.get_or_fetch_wikivoyage(DEST_ID, section)
        assert isinstance(text, str) and text.strip(), f"wikivoyage {section} must be non-empty str"
        _assert_cache_hit(
            lambda s=section: db.get_or_fetch_wikivoyage(DEST_ID, s),
            f"wikivoyage/{section}",
        )
        print(f"wikivoyage/{section:<5} PASS - {len(text)} chars")

    # --- get_or_fetch_fcdo ---------------------------------------------------
    fcdo = db.get_or_fetch_fcdo(DEST_ID)
    assert isinstance(fcdo, dict)
    assert "safety_text" in fcdo and "entry_text" in fcdo
    assert isinstance(fcdo["safety_text"], str) and len(fcdo["safety_text"]) > 100
    _assert_cache_hit(lambda: db.get_or_fetch_fcdo(DEST_ID), "fcdo")
    print(f"fcdo          PASS - safety_text {len(fcdo['safety_text'])} chars")

    # --- get_or_fetch_summary (all four tabs) --------------------------------
    for tab in ("see", "do", "drink", "safety"):
        summary = db.get_or_fetch_summary(DEST_ID, tab, gemini_key)
        assert isinstance(summary, str) and summary.strip(), f"summary/{tab} must be non-empty str"
        assert len(summary) < 2000, f"summary/{tab} unexpectedly long ({len(summary)} chars)"
        _assert_cache_hit(
            lambda t=tab: db.get_or_fetch_summary(DEST_ID, t, gemini_key),
            f"summary/{tab}",
        )
        preview = (
            summary[:120]
            .replace("\n", " ")
            .encode("ascii", errors="replace")
            .decode("ascii")
        )
        print(f"summary/{tab:<7} PASS - {len(summary)} chars - {preview!r}...")

    print()
    print("All get_or_fetch_* orchestrators PASS for destination 123 (Klaipeda).")
