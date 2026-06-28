"""Dashboard view — the rich destination experience.

Top bar: a Back-to-search button plus a switcher to flip between the three
suggested destinations (cheap, because DuckDB caches everything after the first
visit). Below: a hero banner, a tabbed weather panel (Climate / This Week /
Today), a venue map, and a lazy-loaded summary panel (See / Do / Drink / Safety).

Weather tabs: a single ``get_or_fetch_weather`` call returns forecast + climate
together, so the three pills share one fetch — switching pills is pure display,
no extra API calls.

Summary tabs: Streamlit reruns the whole script on every click, so we render
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

try:  # optional — graceful fallback to st.map if not installed
    import folium
    from streamlit_folium import st_folium
    _FOLIUM_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FOLIUM_AVAILABLE = False

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

_WEATHER_TABS: list[tuple[str, str]] = [
    ("climate", "Climate"),
    ("week", "This Week"),
    ("today", "Today"),
]

_VENUE_TABS: list[tuple[str, str]] = [
    ("cafes", "☕ Cafes"),
    ("bars", "🍻 Bars"),
    ("attractions", "🎡 Attractions"),
    ("nightclub", "🕺 Nightclub"),
]

_VENUE_SPINNERS = {
    "cafes": "Searching for nearby cafes…",
    "bars": "Finding local bars…",
    "attractions": "Discovering popular attractions…",
    "nightclub": "Scouting nightclubs…",
}

# Pin colour per venue tab — distinguishable at a glance once pins overlap.
# Deep, theme-adjacent hues that read well at 67% fill opacity with a solid outline.
_VENUE_COLORS = {
    "cafes": "#6F4E37",        # coffee brown
    "bars": "#961717",         # brand claret
    "attractions": "#1F6F5C",  # teal-green
    "nightclub": "#4B2E83",    # plum
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
def _load_google_places(destination_id: int, venue_type: str, _api_key: str) -> list | None:
    try:
        return db.get_or_fetch_google_places(destination_id, venue_type, _api_key)
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


# --- Weather ----------------------------------------------------------------


def _weather_section(destination_id: int) -> None:
    st.markdown('<div class="hp-section-title">Weather &amp; climate</div>', unsafe_allow_html=True)
    with st.spinner("Reading the skies…"):
        weather = _load_weather(destination_id)

    if not weather or "error" in (weather or {}):
        st.info("Weather data isn't available right now.")
        return

    ss = st.session_state
    active = ss.get("active_weather_tab", "climate")

    # Pill selector — one fetch already returned everything, so switching is
    # pure display: no rerun-induced API calls.
    cols = st.columns(len(_WEATHER_TABS))
    for col, (key, label) in zip(cols, _WEATHER_TABS):
        with col:
            if st.button(
                label,
                key=f"weather_tab_{key}",
                type="primary" if key == active else "secondary",
                width="stretch",
            ):
                if key != active:
                    ss["active_weather_tab"] = key
                    st.rerun()

    if active == "week":
        _week_tab(weather)
    elif active == "today":
        _today_tab(weather)
    else:
        _climate_tab(weather)


def _climate_tab(weather: dict) -> None:
    climate = weather.get("climate") or []
    if not climate:
        st.info("Climate data isn't available right now.")
        return

    df = pd.DataFrame(climate)
    if not {"date", "temperature_mean", "precipitation"}.issubset(df.columns):
        st.info("Climate data isn't available right now.")
        return

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    monthly = (
        df.groupby(df["date"].dt.month)
        .agg(temperature=("temperature_mean", "mean"), rainfall=("precipitation", "sum"))
    )
    monthly["month"] = [calendar.month_abbr[m] for m in monthly.index]

    st.caption("Typical monthly climate, averaged across recent years")
    chart_l, chart_r = st.columns(2)
    # Altair (not st.line_chart) so the x-axis follows calendar order — the
    # native charts sort string labels alphabetically.
    with chart_l:
        st.caption("Avg temperature (°C)")
        temp_chart = (
            alt.Chart(monthly)
            .mark_line(point=True, color="#961717")
            .encode(
                x=alt.X("month:N", sort=_MONTH_ORDER, title="Month"),
                y=alt.Y("temperature:Q", title=None),
                tooltip=[
                    alt.Tooltip("month:N", title="Month"),
                    alt.Tooltip("temperature:Q", title="Temperature", format=".1f"),
                ],
            )
            .properties(height=240)
        )
        st.altair_chart(temp_chart, width="stretch")
    with chart_r:
        st.caption("Total rainfall (mm)")
        rain_chart = (
            alt.Chart(monthly)
            .mark_bar(color="#6A8CAF")
            .encode(
                x=alt.X("month:N", sort=_MONTH_ORDER, title="Month"),
                y=alt.Y("rainfall:Q", title=None),
                tooltip=[
                    alt.Tooltip("month:N", title="Month"),
                    alt.Tooltip("rainfall:Q", title="Rainfall", format=".1f"),
                ],
            )
            .properties(height=240)
        )
        st.altair_chart(rain_chart, width="stretch")


def _week_tab(weather: dict) -> None:
    daily = weather.get("forecast", {}).get("daily") or []
    if not daily:
        st.info("No forecast for the week ahead is available.")
        return

    df = pd.DataFrame(daily)
    if not {"date", "temperature_max", "temperature_min", "precipitation"}.issubset(df.columns):
        st.info("No forecast for the week ahead is available.")
        return

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    df["day"] = df["date"].dt.strftime("%a")
    df["day_full"] = df["date"].dt.strftime("%a %d %b")
    day_order = df["day"].tolist()

    # Rain (right axis, faint bars) + max/min temperature lines (left axis).
    # Melt max/min into one series so Altair draws a single left Y axis.
    temp_long = df.melt(
        id_vars=["day", "day_full", "precipitation"],
        value_vars=["temperature_max", "temperature_min"],
        var_name="series",
        value_name="temperature",
    )
    temp_long["series"] = temp_long["series"].map(
        {"temperature_max": "Max", "temperature_min": "Min"}
    )

    base = alt.Chart(df).encode(
        x=alt.X("day:N", sort=day_order, title=None, axis=alt.Axis(labelAngle=0))
    )
    rain = base.mark_bar(color="#9db8d2", opacity=0.45).encode(
        y=alt.Y("precipitation:Q", title="Rain (mm)", axis=alt.Axis(orient="right", titleColor="#6A8CAF")),
        tooltip=[
            alt.Tooltip("day_full:N", title="Day"),
            alt.Tooltip("temperature_max:Q", title="Max temp", format=".1f"),
            alt.Tooltip("temperature_min:Q", title="Min temp", format=".1f"),
            alt.Tooltip("precipitation:Q", title="Rain", format=".1f"),
        ],
    )
    temp = (
        alt.Chart(temp_long)
        .mark_line(point=True)
        .encode(
            x=alt.X("day:N", sort=day_order, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("temperature:Q", title="Max / Min (°C)"),
            color=alt.Color(
                "series:N",
                scale=alt.Scale(domain=["Max", "Min"], range=["#961717", "#6A8CAF"]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            strokeWidth=alt.condition(
                alt.datum.series == "Max", alt.value(3), alt.value(2)
            ),
            tooltip=[
                alt.Tooltip("day_full:N", title="Day"),
                alt.Tooltip("series:N", title=""),
                alt.Tooltip("temperature:Q", title="Temp", format=".1f"),
                alt.Tooltip("precipitation:Q", title="Rain", format=".1f"),
            ],
        )
    )
    chart = alt.layer(rain, temp).resolve_scale(y="independent").properties(height=300)
    st.altair_chart(chart, width="stretch")

    # Compact day strip — one card per forecast day.
    st.caption("Daily breakdown")
    cols = st.columns(len(df))
    for col, row in zip(cols, df.itertuples()):
        with col:
            with st.container(border=True):
                st.markdown(f"**{row.day}**")
                st.markdown(
                    f'<span style="color:#961717;font-size:1.25rem;font-weight:600;">'
                    f"{row.temperature_max:.0f}°</span>"
                    f'<span style="color:rgba(43,38,34,0.55);"> / {row.temperature_min:.0f}°</span>',
                    unsafe_allow_html=True,
                )
                rain_mm = float(row.precipitation) if row.precipitation is not None else 0.0
                st.caption(f"🌧 {rain_mm:.1f} mm")


def _today_tab(weather: dict) -> None:
    # Open-Meteo's `current` block is an instantaneous snapshot at the moment
    # the API answered — not a daily high/low. Surface that clearly but quietly.
    current = weather.get("forecast", {}).get("current", {})
    st.caption("Live snapshot — readings at the moment the data was fetched, not daily highs/lows.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Temperature", f"{current.get('temperature', float('nan')):.0f}°C")
    c2.metric("Humidity", f"{current.get('humidity', float('nan')):.0f}%")
    c3.metric("Cloud cover", f"{current.get('cloud_cover', float('nan')):.0f}%")
    c4.metric("Wind", f"{current.get('wind_speed', float('nan')):.0f} km/h")


# --- Venues -----------------------------------------------------------------


def _venue_popup_html(venue: dict, meta: str) -> str:
    name = html.escape(str(venue.get("name", "Unknown")))
    address = html.escape(str(venue.get("address", "")))
    maps_uri = venue.get("google_maps_uri") or ""
    return (
        '<div style="font-family:Fraunces,Georgia,serif;color:#2B2622;min-width:210px;">'
        f'<div style="font-size:15px;font-weight:600;margin-bottom:4px;">{name}</div>'
        f'<div style="font-size:13px;margin-bottom:4px;">{meta}</div>'
        f'<div style="font-size:12px;color:rgba(43,38,34,0.62);margin-bottom:10px;">{address}</div>'
        f'<a href="{maps_uri}" target="_blank" rel="noopener" '
        'style="display:inline-block;background:#961717;color:#fff;text-decoration:none;'
        'padding:6px 14px;border-radius:999px;font-size:12px;font-family:Fraunces,serif;">'
        "Open in Google Maps ↗</a></div>"
    )


# Custom map pin rendered as SVG so we can control opacity + a crisp outline
# (overlapping pins stay distinguishable). Color shifts per venue category.
_PIN_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" '
    'viewBox="0 0 24 24" fill="{fill}" fill-opacity="0.67" stroke="{stroke}" '
    'stroke-width="2" stroke-linejoin="round">'
    '<path d="M12 2C7.6 2 4 5.6 4 10c0 5.4 7 11.5 7.3 11.8 .2 .2 .5 .2 .7 0 '
    'C12.3 21.5 20 15.4 20 10c0-4.4-3.6-8-8-8z"/>'
    '<circle cx="12" cy="10" r="3" fill="#fff" fill-opacity="0.9" stroke="none"/>'
    '</svg>'
)


def _venue_pin_icon(category: str) -> folium.DivIcon:
    color = _VENUE_COLORS.get(category, "#961717")
    svg = _PIN_SVG.format(fill=color, stroke=color)
    return folium.DivIcon(
        html=svg,
        icon_size=(28, 28),
        icon_anchor=(14, 28),
        popup_anchor=(0, -26),
        class_name="hp-venue-pin",
    )


def _render_venue_map(dest: dict, venues: list, venue_type: str) -> None:
    # Larger, taller map that fills the column; scroll zoom re-enabled so users
    # can drill in/out. fit_bounds recentres on the pins (not just the dest
    # centroid) so clusters aren't clipped off the edges.
    m = folium.Map(
        location=[dest["lat"], dest["lng"]],
        zoom_start=14,
        scrollWheelZoom=True,
        zoom_control=True,
        tiles="CartoDB positron",
        control_scale=True,
    )

    bounds: list[list[float]] = []
    for v in venues:
        if v.get("business_status") == "CLOSED_PERMANENTLY":
            continue  # don't send users to dead venues
        lat, lng = v.get("lat"), v.get("lng")
        if lat is None or lng is None:
            continue

        name = html.escape(str(v.get("name", "Unknown")))
        primary_type = html.escape(str(v.get("primary_type", "Venue")))
        accessible = bool(v.get("wheelchair_accessible"))
        closed_temp = v.get("business_status") == "CLOSED_TEMPORARILY"

        # Hover = just the name (cheap, no clutter). Click = full popup.
        tooltip = folium.Tooltip(
            f'<div style="font-family:Fraunces,serif;font-size:13px;">'
            f'<b>{name}</b></div>',
            sticky=False,
        )

        meta_parts = [primary_type]
        if accessible:
            meta_parts.append("♿ Accessible")
        if closed_temp:
            meta_parts.append('<span style="color:#961717;font-weight:600;">Temporarily closed</span>')
        meta = " · ".join(meta_parts)

        popup = folium.Popup(_venue_popup_html(v, meta), max_width=320)
        folium.Marker(
            location=[lat, lng],
            tooltip=tooltip,
            popup=popup,
            icon=_venue_pin_icon(venue_type),
        ).add_to(m)
        bounds.append([lat, lng])

    # Recenter + rezoom around the actual pins so nothing sits off-canvas.
    if bounds:
        m.fit_bounds(bounds, padding=(40, 40))
    else:
        m.location = [dest["lat"], dest["lng"]]

    st_folium(
        m,
        height=560,
        width="stretch",  # fill the column width responsively
        returned_objects=[],
    )


def _venues_section(destination_id: int) -> None:
    st.markdown('<div class="hp-section-title">Eat, drink &amp; explore nearby</div>', unsafe_allow_html=True)

    api_key = st.secrets.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        st.info("Add a `GOOGLE_PLACES_API_KEY` to view the venue map.")
        return

    ss = st.session_state
    active_venue = ss.get("active_venue_tab", "cafes")

    # Venue tab selector — a row of pill buttons. Only the active tab's content is
    # rendered below, so non-active tabs never trigger an API/LLM call.
    cols = st.columns(len(_VENUE_TABS))
    for col, (tab_key, label) in zip(cols, _VENUE_TABS):
        with col:
            if st.button(
                label,
                key=f"venue_tab_{tab_key}",
                type="primary" if tab_key == active_venue else "secondary",
                width="stretch",
            ):
                if tab_key != active_venue:
                    ss["active_venue_tab"] = tab_key
                    st.rerun()

    with st.spinner(_VENUE_SPINNERS.get(active_venue, "Scouting local spots…")):
        venues = _load_google_places(destination_id, active_venue, api_key)

    if isinstance(venues, dict) and "error" in venues:
        st.info("Venue data isn't available right now.")
        return
    if not venues:
        st.info("No nearby venues found for this category.")
        return

    st.caption(
        f"{len(venues)} places found — hover a pin to see its name, "
        "click it for the type, address and a Google Maps link."
    )

    if _FOLIUM_AVAILABLE:
        dest = db.get_destination(destination_id)
        _render_venue_map(dest, venues, active_venue)
    else:
        df = pd.DataFrame(venues)
        coords = df.dropna(subset=["lat", "lng"]).rename(columns={"lng": "lon"})
        if not coords.empty:
            st.map(coords[["lat", "lon"]], width="stretch")
        st.info("Install `streamlit-folium` for the interactive pin map with popups.")


# --- Summaries --------------------------------------------------------------


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
                width="stretch",
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
        if st.button("← Back to search", width="stretch"):
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
                    width="stretch",
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
    _summaries_section(dest_id)
    _venues_section(dest_id)
