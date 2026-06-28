"""Dashboard view — the rich destination experience.

Top bar: a Back-to-search button plus a switcher to flip between the three
suggested destinations (cheap, because DuckDB caches everything after the first
visit). Below: a hero banner, current weather, a seasonal climate chart, a
venue map, and a lazy-loaded summary panel (See / Do / Drink / Safety).

Lazy loading: Streamlit reruns the whole script on every click, so we render
*only* the active summary tab. Opening "Safety" reruns, sets the active tab,
and only then triggers that one LLM/scrape call (with a fun spinner). "See"
loads by default; the others wait until clicked.
"""

from __future__ import annotations

import calendar
import html

import altair as alt
import pandas as pd
import streamlit as st

import theme
from src import database as db

_MONTH_ORDER = list(calendar.month_abbr)[1:]  # ["Jan", ..., "Dec"]

_TABS: list[tuple[str, str]] = [
    ("see", "See"),
    ("do", "Do"),
    ("drink", "Drink"),
    ("safety", "Safety"),
]

_TAB_SPINNERS = {
    "see": "Rounding up the sights…",
    "do": "Digging up things to do…",
    "drink": "Finding a good watering hole…",
    "safety": "Checking the latest travel advice…",
}


# --- Cached loaders ---------------------------------------------------------
# Caching keyed on destination_id keeps reruns (e.g. clicking a tab) from
# re-reading the DB / re-hitting APIs. The api_key arg is underscore-prefixed
# so Streamlit excludes it from the cache key.


@st.cache_data(show_spinner=False)
def _load_weather(destination_id: int) -> dict | None:
    try:
        return db.get_or_fetch_weather(destination_id)
    except Exception as exc:  # noqa: BLE001 — surface as a friendly UI message
        return {"error": str(exc)}


@st.cache_data(show_spinner=False)
def _load_places(destination_id: int, _api_key: str) -> list | None:
    try:
        return db.get_or_fetch_places(destination_id, _api_key)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@st.cache_data(show_spinner=False)
def _load_summary(destination_id: int, tab: str, _api_key: str) -> str:
    return db.get_or_fetch_summary(destination_id, tab, _api_key)


# --- Sections ---------------------------------------------------------------


def _hero(dest: dict) -> None:
    bg = theme.image_css_value(int(dest["id"]))
    name = html.escape(str(dest["name"]))
    country = html.escape(str(dest["country"]))
    region = html.escape(str(dest["region"]))
    st.markdown(
        f'<div class="hp-hero" style="background-image:{bg};">'
        '<div class="hp-hero-content">'
        f'<p class="hp-hero-name">{name}</p>'
        f'<p class="hp-hero-meta">{country} · {region}</p>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _weather_section(destination_id: int) -> None:
    st.markdown('<div class="hp-section-title">Weather &amp; climate</div>', unsafe_allow_html=True)
    with st.spinner("Reading the skies…"):
        weather = _load_weather(destination_id)

    if not weather or "error" in (weather or {}):
        st.info("Weather data isn't available right now.")
        return

    current = weather.get("forecast", {}).get("current", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Temperature", f"{current.get('temperature', float('nan')):.0f}°C")
    c2.metric("Humidity", f"{current.get('humidity', float('nan')):.0f}%")
    c3.metric("Cloud cover", f"{current.get('cloud_cover', float('nan')):.0f}%")
    c4.metric("Wind", f"{current.get('wind_speed', float('nan')):.0f} km/h")

    climate = weather.get("climate") or []
    if not climate:
        return

    df = pd.DataFrame(climate)
    if {"date", "temperature_mean", "precipitation"}.issubset(df.columns):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        monthly = (
            df.groupby(df["date"].dt.month)
            .agg(temp=("temperature_mean", "mean"), rain=("precipitation", "sum"))
        )
        monthly["month"] = [calendar.month_abbr[m] for m in monthly.index]

        st.caption("Typical monthly climate (2025)")
        chart_l, chart_r = st.columns(2)
        # Altair (not st.line_chart) so the x-axis follows calendar order — the
        # native charts sort string labels alphabetically.
        with chart_l:
            st.caption("Avg temperature (°C)")
            temp_chart = (
                alt.Chart(monthly)
                .mark_line(point=True, color="#C2683A")
                .encode(
                    x=alt.X("month:N", sort=_MONTH_ORDER, title=None),
                    y=alt.Y("temp:Q", title=None),
                )
                .properties(height=220)
            )
            st.altair_chart(temp_chart, use_container_width=True)
        with chart_r:
            st.caption("Total rainfall (mm)")
            rain_chart = (
                alt.Chart(monthly)
                .mark_bar(color="#6A8CAF")
                .encode(
                    x=alt.X("month:N", sort=_MONTH_ORDER, title=None),
                    y=alt.Y("rain:Q", title=None),
                )
                .properties(height=220)
            )
            st.altair_chart(rain_chart, use_container_width=True)


def _venues_section(destination_id: int) -> None:
    st.markdown('<div class="hp-section-title">Eat, drink &amp; explore nearby</div>', unsafe_allow_html=True)

    api_key = st.secrets.get("GEOAPIFY_API_KEY")
    if not api_key:
        st.info("Add a `GEOAPIFY_API_KEY` to view the venue map.")
        return

    with st.spinner("Scouting local venues…"):
        venues = _load_places(destination_id, api_key)

    if isinstance(venues, dict) and "error" in venues:
        st.info("Venue data isn't available right now.")
        return
    if not venues:
        st.info("No nearby venues found for this spot.")
        return

    df = pd.DataFrame(venues)
    coords = df.dropna(subset=["lat", "lng"]).rename(columns={"lng": "lon"})
    if not coords.empty:
        st.map(coords[["lat", "lon"]], use_container_width=True)

    if "category" in df.columns:
        counts = df["category"].value_counts()
        cols = st.columns(len(counts) or 1)
        for col, (category, n) in zip(cols, counts.items()):
            col.metric(str(category).title(), int(n))


def _summaries_section(destination_id: int) -> None:
    ss = st.session_state
    st.markdown('<div class="hp-section-title">The lowdown</div>', unsafe_allow_html=True)

    active = ss.get("active_tab", "see")

    # Tab selector — a row of pill buttons. Only the active tab's content is
    # rendered below, so non-active tabs never trigger an API/LLM call.
    cols = st.columns(len(_TABS))
    for col, (tab_key, label) in zip(cols, _TABS):
        with col:
            if st.button(
                label,
                key=f"tab_{tab_key}",
                type="primary" if tab_key == active else "secondary",
                use_container_width=True,
            ):
                if tab_key != active:
                    ss["active_tab"] = tab_key
                    st.rerun()

    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.info("Add a `GEMINI_API_KEY` to generate the summaries.")
        return

    with st.spinner(_TAB_SPINNERS.get(active, "Loading…")):
        try:
            summary = _load_summary(destination_id, active, api_key)
            error = None
        except Exception as exc:  # noqa: BLE001
            summary, error = None, exc

    if summary:
        st.markdown(summary)
    elif error is not None:
        st.warning("This summary isn't available right now.")
        with st.expander("Details"):
            st.exception(error)
    else:
        st.info("This summary isn't available right now — try another tab.")


def _top_bar(dest_id: int) -> None:
    ss = st.session_state
    back_col, switch_col = st.columns([1.1, 3])

    with back_col:
        if st.button("← Back to search", use_container_width=True):
            ss["view"] = "search"
            st.rerun()

    with switch_col:
        ids = ss.get("suggestion_ids") or [dest_id]
        cols = st.columns(len(ids))
        for col, i in zip(cols, ids):
            other = db.get_destination(int(i))
            if not other:
                continue
            with col:
                if st.button(
                    other["name"],
                    key=f"switch_{i}",
                    type="primary" if int(i) == dest_id else "secondary",
                    use_container_width=True,
                ):
                    if int(i) != dest_id:
                        ss["selected_destination_id"] = int(i)
                        ss["active_tab"] = "see"
                        st.rerun()


def render() -> None:
    ss = st.session_state
    dest_id = int(ss["selected_destination_id"])
    dest = db.get_destination(dest_id)
    if not dest:
        st.error("That destination could not be found.")
        if st.button("← Back to search"):
            ss["view"] = "search"
            st.rerun()
        return

    _top_bar(dest_id)
    _hero(dest)
    _weather_section(dest_id)
    _venues_section(dest_id)
    _summaries_section(dest_id)
