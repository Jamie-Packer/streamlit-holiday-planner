"""Search view — describe a dream holiday, get three destination cards.

The chat-style input sits vertically centred until results exist, then the
page reflows: input at the top, three image cards below. No spoiler caption —
the cards appear only once the LLM has chosen them.
"""

from __future__ import annotations

import html

import streamlit as st

import theme
from src import database as db
from src.llm import route_destinations


def _route(prompt: str) -> list[int]:
    """Ask Gemini for three matching destination IDs (lat/lng stripped from catalogue)."""
    catalogue = [
        {k: v for k, v in row.items() if k not in ("lat", "lng")}
        for row in db.get_all_destinations()
    ]
    return route_destinations(prompt, catalogue, st.secrets["GEMINI_API_KEY"])


def _card_html(dest: dict) -> str:
    name = html.escape(str(dest["name"]))
    country = html.escape(str(dest["country"]))
    region = html.escape(str(dest["region"]))
    bg = theme.image_css_value(int(dest["id"]))
    return (
        '<div class="hp-card">'
        f'<div class="hp-card-img" style="background-image:{bg};"></div>'
        '<div class="hp-card-body">'
        f'<p class="hp-card-name">{name}</p>'
        f'<p class="hp-card-country">{country}</p>'
        f'<p class="hp-card-region">{region}</p>'
        '</div>'
        '</div>'
    )


def render() -> None:
    ss = st.session_state
    has_results = bool(ss.get("suggestion_ids"))

    # Push the title/input down into the vertical centre before any results.
    if not has_results:
        st.markdown('<div class="hp-spacer-lg"></div>', unsafe_allow_html=True)

    st.markdown('<h1 class="hp-search-title">Where shall we send you?</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hp-search-sub">Describe your ideal holiday in your own words.</p>',
        unsafe_allow_html=True,
    )

    left, centre, right = st.columns([1, 2, 1])
    with centre:
        with st.form("search_form", clear_on_submit=False, border=False):
            prompt = st.text_input(
                "Your holiday",
                value=ss.get("search_prompt", ""),
                placeholder="e.g. warm beaches, lively nightlife and great seafood…",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Find my destinations", width="stretch")

    if submitted:
        if not prompt.strip():
            st.warning("Tell us a little about your ideal holiday first.")
        else:
            ss["search_prompt"] = prompt
            with st.spinner("Consulting the atlas…"):
                ss["suggestion_ids"] = _route(prompt)
            st.rerun()

    if not has_results:
        return

    st.markdown('<div class="hp-section-title">Three places picked for you</div>', unsafe_allow_html=True)
    ids = ss["suggestion_ids"]
    cols = st.columns(len(ids))
    for col, dest_id in zip(cols, ids):
        dest = db.get_destination(int(dest_id))
        if not dest:
            continue
        with col:
            st.markdown(_card_html(dest), unsafe_allow_html=True)
            if st.button(
                f"Explore {dest['name']}",
                key=f"explore_{dest_id}",
                width="stretch",
            ):
                ss["selected_destination_id"] = int(dest_id)
                ss["active_tab"] = "see"
                ss["view"] = "dashboard"
                st.rerun()
