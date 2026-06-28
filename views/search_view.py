"""Search view — describe a dream holiday, get three destination cards.

The chat-style input sits vertically centred until results exist, then the
page reflows: input at the top, three image cards below. No spoiler caption —
the cards appear only once the LLM has chosen them.

The input is a plain ``st.text_input`` (no ``st.form``) so Streamlit doesn't
render its "Press enter to submit form" hint; Enter still submits via an
``on_change`` callback. Each result card is a styled HTML card (image + name)
followed immediately by a real, visible ``st.button`` labelled "Explore <name>".
Clicking that button flips ``view`` to ``"dashboard"`` via ``st.rerun()`` — an
in-app transition (no new tab, no ``<a href>``) so ``suggestion_ids`` survives
into the dashboard's top tab bar. A hyperlink reload would wipe session state
(see the dev log).
"""

from __future__ import annotations

import html
import random

import streamlit as st

import theme
from src import database as db
from src.llm import route_destinations

# Rotating hero lines — one is picked per session so it doesn't flicker on
# every rerun.
_PHRASES = [
    "What kind of place do you need?",
    "Consult your dreams.",
    "What's the holiday vibe?",
    "Describe your perfect escape.",
    "Where to next?",
    "Tell me the place you're craving.",
    "Paint me a picture of your ideal trip.",
    "What's the adventure?",
    "Where's your mind wandering?",
    "Sell me on a holiday.",
]


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

    # Initialise the input from any previous prompt so a return trip shows text.
    ss.setdefault("search_input", ss.get("search_prompt", ""))

    # Push the title/input down into the vertical centre before any results.
    if not has_results:
        st.markdown('<div class="hp-spacer-lg"></div>', unsafe_allow_html=True)

    hero = ss.setdefault("hero_phrase", random.choice(_PHRASES))
    st.markdown(f'<h1 class="hp-search-title">{html.escape(hero)}</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hp-search-sub">Describe your ideal holiday in your own words.</p>',
        unsafe_allow_html=True,
    )

    left, centre, right = st.columns([1, 2, 1])
    with centre:
        def _mark_pending() -> None:
            ss["search_pending"] = bool((ss.get("search_input") or "").strip())

        st.text_input(
            "Your holiday",
            placeholder="e.g. warm beaches, lively nightlife and great seafood…",
            label_visibility="collapsed",
            key="search_input",
            on_change=_mark_pending,
        )
        if st.button("Find my destinations", type="primary", width="stretch"):
            _mark_pending()

    if ss.get("search_pending"):
        ss["search_pending"] = False
        prompt = (ss.get("search_input") or "").strip()
        if not prompt:
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
            # The card markup is purely visual; the st.button rendered right
            # below it is what actually carries the click. Wrapping both in a
            # single st.container means they render as one unit per column.
            # In-app navigation only — no <a href>, so session_state (and
            # suggestion_ids, which the dashboard top bar relies on) survives
            # the rerun. See the dev log for why hyperlink nav was rejected.
            with st.container():
                st.markdown(_card_html(dest), unsafe_allow_html=True)
                if st.button(
                    f"Explore {dest['name']}",
                    key=f"explore_{dest_id}",
                    type="primary",
                    width="stretch",
                ):
                    ss["selected_destination_id"] = int(dest_id)
                    ss["active_tab"] = "see"
                    ss["view"] = "dashboard"
                    st.rerun()
