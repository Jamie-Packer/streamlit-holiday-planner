"""DuckDB connection, schema, and all read/write functions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "planner.db"
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "destinations.csv"

WIKIVOYAGE_SECTIONS = frozenset({"See", "Do", "Drink"})
SUMMARY_TAB_TYPES = frozenset({"see", "do", "drink", "safety"})


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
                id       INTEGER PRIMARY KEY,
                name     VARCHAR,
                country  VARCHAR,
                region   VARCHAR,
                lat      DOUBLE,
                lng      DOUBLE,
                tags     VARCHAR
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


def get_destination(destination_id: int) -> dict | None:
    """Return a single destination row or None if not found."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, name, country, region, lat, lng, tags
            FROM destinations
            WHERE id = ?
            """,
            [destination_id],
        ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row, ["id", "name", "country", "region", "lat", "lng", "tags"])
    finally:
        conn.close()


def get_all_destinations() -> list[dict]:
    """Return all destinations for LLM routing."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, name, country, region, lat, lng, tags
            FROM destinations
            ORDER BY id
            """
        ).fetchall()
        columns = ["id", "name", "country", "region", "lat", "lng", "tags"]
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
                json.dumps(forecast),
                json.dumps(climate),
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


def get_or_fetch_weather(destination_id: int) -> dict:
    """Return cached weather or fetch and save on miss. Implemented in Phase 2."""
    raise NotImplementedError


def get_or_fetch_places(destination_id: int, api_key: str) -> list:
    """Return cached venues or fetch and save on miss. Implemented in Phase 2."""
    raise NotImplementedError


def get_or_fetch_wikivoyage(destination_id: int, section: str) -> str:
    """Return cached Wikivoyage section or fetch and save on miss. Implemented in Phase 2."""
    raise NotImplementedError


def get_or_fetch_fcdo(destination_id: int) -> dict:
    """Return cached FCDO advice or fetch and save on miss. Implemented in Phase 2."""
    raise NotImplementedError


def get_or_fetch_summary(destination_id: int, tab_type: str, api_key: str) -> str:
    """Return cached tab summary or generate and save on miss. Implemented in Phase 2."""
    raise NotImplementedError


if __name__ == "__main__":
    init_db()
    print(f"Seeded {len(get_all_destinations())} destinations")
