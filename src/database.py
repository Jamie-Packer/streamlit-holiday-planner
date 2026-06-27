"""DuckDB connection, schema, and all read/write functions.

This module is the single point of contact between the Streamlit frontend
(`pages/`, `Home.py`) and the data layer. Fetching happens in `src/` modules;
this module owns the cache, JSON serialisation, and the `get_or_fetch_*`
orchestrator pattern:

    cache hit  → return cached row
    cache miss → fetch via src/ module → save_* → return get_* (round-trip)

Round-tripping through the DB guarantees the UI always reads the same shape
whether the data was cached or freshly fetched, and validates JSON
serialisation on the very first fetch rather than at display time.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "planner.db"
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "destinations.csv"

WIKIVOYAGE_SECTIONS = frozenset({"See", "Do", "Drink"})
SUMMARY_TAB_TYPES = frozenset({"see", "do", "drink", "safety"})

# Map summary tab_type → Wikivoyage section title (case-sensitive in the API).
_TAB_TO_WIKIVOYAGE_SECTION = {
    "see": "See",
    "do": "Do",
    "drink": "Drink",
}


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a connection to the embedded DuckDB database."""
    return duckdb.connect(str(DB_PATH))


def init_db() -> None:
    """Create tables if missing and seed destinations from CSV when empty."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS destinations (
                id              INTEGER PRIMARY KEY,
                name            VARCHAR,
                country         VARCHAR,
                region          VARCHAR,
                lat             DOUBLE,
                lng             DOUBLE,
                tags            VARCHAR,
                gov_uk_country  VARCHAR
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weather (
                destination_id  INTEGER PRIMARY KEY,
                fetched_at      TIMESTAMP,
                forecast_json   VARCHAR,
                climate_json    VARCHAR
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS places (
                destination_id  INTEGER PRIMARY KEY,
                fetched_at      TIMESTAMP,
                venues_json     VARCHAR
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wikivoyage (
                destination_id  INTEGER,
                section         VARCHAR,
                fetched_at      TIMESTAMP,
                raw_text        VARCHAR,
                PRIMARY KEY (destination_id, section)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fcdo (
                destination_id  INTEGER PRIMARY KEY,
                fetched_at      TIMESTAMP,
                safety_text     VARCHAR,
                entry_text      VARCHAR
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                destination_id  INTEGER,
                tab_type        VARCHAR,
                fetched_at      TIMESTAMP,
                summary_text    VARCHAR,
                PRIMARY KEY (destination_id, tab_type)
            )
            """
        )

        count = conn.execute("SELECT COUNT(*) FROM destinations").fetchone()[0]
        if count == 0:
            conn.execute(
                f"""
                INSERT INTO destinations
                SELECT * FROM read_csv_auto('{CSV_PATH.as_posix()}', header=true)
                """
            )
    finally:
        conn.close()


def _row_to_dict(row: tuple, columns: list[str]) -> dict:
    return dict(zip(columns, row))


def _json_default(obj):
    """JSON fallback for numpy/pandas scalars that aren't native Python types."""
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if hasattr(obj, "item"):  # numpy scalar → native Python
        return obj.item()
    if hasattr(obj, "tolist"):  # numpy array
        return obj.tolist()
    try:
        if pd.isna(obj):  # NaN / NaT
            return None
    except (TypeError, ValueError):
        pass
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")


def _df_to_records(df) -> list[dict]:
    """Convert a pandas DataFrame to a JSON-safe list of dict records.

    Datetime columns are stringified to ISO date strings; numpy scalars are
    coerced to native Python via `_json_default` at dump time.
    """
    if df is None or getattr(df, "empty", True):
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    return out.to_dict(orient="records")


def get_destination(destination_id: int) -> dict | None:
    """Return a single destination row or None if not found."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, name, country, region, lat, lng, tags, gov_uk_country
            FROM destinations
            WHERE id = ?
            """,
            [destination_id],
        ).fetchone()
        if row is None:
            return None
        return _row_to_dict(
            row,
            ["id", "name", "country", "region", "lat", "lng", "tags", "gov_uk_country"],
        )
    finally:
        conn.close()


def get_all_destinations() -> list[dict]:
    """Return all destinations for LLM routing."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, name, country, region, lat, lng, tags, gov_uk_country
            FROM destinations
            ORDER BY id
            """
        ).fetchall()
        columns = ["id", "name", "country", "region", "lat", "lng", "tags", "gov_uk_country"]
        return [_row_to_dict(row, columns) for row in rows]
    finally:
        conn.close()


def get_weather(destination_id: int) -> dict | None:
    """Return cached weather as {"forecast": dict, "climate": dict} or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT forecast_json, climate_json
            FROM weather
            WHERE destination_id = ?
            """,
            [destination_id],
        ).fetchone()
        if row is None:
            return None
        return {
            "forecast": json.loads(row[0]),
            "climate": json.loads(row[1]),
        }
    finally:
        conn.close()


def save_weather(destination_id: int, forecast: dict, climate: dict) -> None:
    """Persist forecast and climate payloads as JSON strings."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO weather (destination_id, fetched_at, forecast_json, climate_json)
            VALUES (?, ?, ?, ?)
            """,
            [
                destination_id,
                datetime.now(timezone.utc),
                json.dumps(forecast, default=_json_default),
                json.dumps(climate, default=_json_default),
            ],
        )
    finally:
        conn.close()


def get_places(destination_id: int) -> list | None:
    """Return cached venue list or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT venues_json
            FROM places
            WHERE destination_id = ?
            """,
            [destination_id],
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])
    finally:
        conn.close()


def save_places(destination_id: int, venues: list) -> None:
    """Persist venue list as JSON string."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO places (destination_id, fetched_at, venues_json)
            VALUES (?, ?, ?)
            """,
            [destination_id, datetime.now(timezone.utc), json.dumps(venues)],
        )
    finally:
        conn.close()


def get_wikivoyage(destination_id: int, section: str) -> str | None:
    """Return cached Wikivoyage section text or None."""
    if section not in WIKIVOYAGE_SECTIONS:
        raise ValueError(f"section must be one of {sorted(WIKIVOYAGE_SECTIONS)}")
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT raw_text
            FROM wikivoyage
            WHERE destination_id = ? AND section = ?
            """,
            [destination_id, section],
        ).fetchone()
        if row is None:
            return None
        return row[0]
    finally:
        conn.close()


def save_wikivoyage(destination_id: int, section: str, raw_text: str) -> None:
    """Persist Wikivoyage section text."""
    if section not in WIKIVOYAGE_SECTIONS:
        raise ValueError(f"section must be one of {sorted(WIKIVOYAGE_SECTIONS)}")
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO wikivoyage (destination_id, section, fetched_at, raw_text)
            VALUES (?, ?, ?, ?)
            """,
            [destination_id, section, datetime.now(timezone.utc), raw_text],
        )
    finally:
        conn.close()


def get_fcdo(destination_id: int) -> dict | None:
    """Return cached FCDO advice as {"safety_text": str, "entry_text": str} or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT safety_text, entry_text
            FROM fcdo
            WHERE destination_id = ?
            """,
            [destination_id],
        ).fetchone()
        if row is None:
            return None
        return {"safety_text": row[0], "entry_text": row[1]}
    finally:
        conn.close()


def save_fcdo(destination_id: int, safety_text: str, entry_text: str) -> None:
    """Persist FCDO safety and entry requirement text."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO fcdo (destination_id, fetched_at, safety_text, entry_text)
            VALUES (?, ?, ?, ?)
            """,
            [destination_id, datetime.now(timezone.utc), safety_text, entry_text],
        )
    finally:
        conn.close()


def get_summary(destination_id: int, tab_type: str) -> str | None:
    """Return cached LLM summary for a tab or None."""
    tab_type = tab_type.lower()
    if tab_type not in SUMMARY_TAB_TYPES:
        raise ValueError(f"tab_type must be one of {sorted(SUMMARY_TAB_TYPES)}")
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT summary_text
            FROM summaries
            WHERE destination_id = ? AND tab_type = ?
            """,
            [destination_id, tab_type],
        ).fetchone()
        if row is None:
            return None
        return row[0]
    finally:
        conn.close()


def save_summary(destination_id: int, tab_type: str, summary_text: str) -> None:
    """Persist LLM-generated tab summary."""
    tab_type = tab_type.lower()
    if tab_type not in SUMMARY_TAB_TYPES:
        raise ValueError(f"tab_type must be one of {sorted(SUMMARY_TAB_TYPES)}")
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO summaries (destination_id, tab_type, fetched_at, summary_text)
            VALUES (?, ?, ?, ?)
            """,
            [destination_id, tab_type, datetime.now(timezone.utc), summary_text],
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Orchestrators — cache miss → fetch → save → return get_* (round-trip)
# ---------------------------------------------------------------------------


def get_or_fetch_weather(destination_id: int) -> dict:
    """Return cached weather or fetch and save on miss.

    `fetch_forecast` returns a dict with a pandas DataFrame under `daily`;
    `fetch_climate` returns a DataFrame. Both are normalised to JSON-safe
    records before being persisted via `save_weather`. The returned shape
    matches `get_weather`: `{"forecast": {...}, "climate": [...]}`.
    """
    cached = get_weather(destination_id)
    if cached is not None:
        return cached

    dest = get_destination(destination_id)
    if dest is None:
        raise ValueError(f"destination_id {destination_id} not found")

    # Imported here so the module loads even if openmeteo isn't installed
    # (e.g. quick DB inspection in a minimal env).
    from src.weather import fetch_climate, fetch_forecast

    forecast_raw = fetch_forecast(dest["lat"], dest["lng"])
    climate_df = fetch_climate(dest["lat"], dest["lng"])

    forecast = {
        "latitude": forecast_raw.get("latitude"),
        "longitude": forecast_raw.get("longitude"),
        "current": forecast_raw.get("current", {}),
        "daily": _df_to_records(forecast_raw.get("daily")),
    }
    climate = _df_to_records(climate_df)

    save_weather(destination_id, forecast, climate)
    return get_weather(destination_id)


def get_or_fetch_places(destination_id: int, api_key: str) -> list:
    """Return cached venues or fetch and save on miss."""
    cached = get_places(destination_id)
    if cached is not None:
        return cached

    dest = get_destination(destination_id)
    if dest is None:
        raise ValueError(f"destination_id {destination_id} not found")

    from src.places import fetch_venues

    venues = fetch_venues(dest["lat"], dest["lng"], api_key)
    save_places(destination_id, venues)
    return get_places(destination_id)


def get_or_fetch_wikivoyage(destination_id: int, section: str) -> str:
    """Return cached Wikivoyage section or fetch and save on miss."""
    if section not in WIKIVOYAGE_SECTIONS:
        raise ValueError(f"section must be one of {sorted(WIKIVOYAGE_SECTIONS)}")

    cached = get_wikivoyage(destination_id, section)
    if cached is not None:
        return cached

    dest = get_destination(destination_id)
    if dest is None:
        raise ValueError(f"destination_id {destination_id} not found")

    from src.wikivoyage import fetch_section

    raw_text = fetch_section(dest["name"], section)
    save_wikivoyage(destination_id, section, raw_text)
    return get_wikivoyage(destination_id, section)


def get_or_fetch_fcdo(destination_id: int) -> dict:
    """Return cached FCDO advice or fetch and save on miss."""
    cached = get_fcdo(destination_id)
    if cached is not None:
        return cached

    dest = get_destination(destination_id)
    if dest is None:
        raise ValueError(f"destination_id {destination_id} not found")

    from src.scraper import fetch_fcdo_advice

    advice = fetch_fcdo_advice(dest.get("gov_uk_country") or "")
    save_fcdo(destination_id, advice.get("safety_text", ""), advice.get("entry_text", ""))
    return get_fcdo(destination_id)


def get_or_fetch_summary(destination_id: int, tab_type: str, api_key: str) -> str:
    """Return cached tab summary or generate and save on miss.

    For see/do/drink: pulls raw text via `get_or_fetch_wikivoyage` (which
    caches the section), then `summarise_tab`. For safety: pulls raw text via
    `get_or_fetch_fcdo` (caches the scrape), then `summarise_tab`. The raw
    text and the summary are both cached in DuckDB, so a repeat visit costs
    zero API/LLM calls.
    """
    tab = tab_type.lower().strip()
    if tab not in SUMMARY_TAB_TYPES:
        raise ValueError(f"tab_type must be one of {sorted(SUMMARY_TAB_TYPES)}")

    cached = get_summary(destination_id, tab)
    if cached is not None:
        return cached

    from src.llm import summarise_tab

    if tab in _TAB_TO_WIKIVOYAGE_SECTION:
        section = _TAB_TO_WIKIVOYAGE_SECTION[tab]
        raw_text = get_or_fetch_wikivoyage(destination_id, section)
    else:  # safety
        fcdo = get_or_fetch_fcdo(destination_id)
        raw_text = fcdo.get("safety_text", "")

    summary = summarise_tab(raw_text, tab, api_key)
    save_summary(destination_id, tab, summary)
    return get_summary(destination_id, tab)


if __name__ == "__main__":
    init_db()
    print(f"Seeded {len(get_all_destinations())} destinations")
