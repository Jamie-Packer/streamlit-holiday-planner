"""Search page — describe a dream holiday, get 3 destination suggestions."""

from __future__ import annotations

import streamlit as st

from src import database as db
from src.llm import route_destinations

st.set_page_config(page_title="Search — Holiday Planner", layout="wide")

# --- Styles ------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&display=swap');

    .search-title {
        font-family: 'Fraunces', Georgia, 'Times New Roman', serif;
        font-size: 3rem;
        font-weight: 600;
        text-align: center;
        margin-top: 1.5rem;
        margin-bottom: 1.5rem;
        letter-spacing: -0.01em;
    }

    .search-subtitle {
        font-family: 'Fraunces', Georgia, serif;
        font-size: 1rem;
        text-align: center;
        color: rgba(60, 60, 60, 0.7);
        margin-bottom: 2rem;
    }

    .suggestion-grid {
        display: flex;
        gap: 1.25rem;
        justify-content: center;
        flex-wrap: wrap;
        margin-top: 2rem;
    }

    .suggestion-card {
        flex: 1 1 280px;
        max-width: 340px;
        min-height: 180px;
        border-radius: 18px;
        background: linear-gradient(160deg, #ffffff 0%, #f6f3ee 100%);
        border: 1px solid rgba(0, 0, 0, 0.06);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
        padding: 1.75rem 1.5rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        text-align: center;
        animation: fadeInUp 0.6s ease both;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }

    .suggestion-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.1);
    }

    .suggestion-name {
        font-family: 'Fraunces', Georgia, serif;
        font-size: 1.6rem;
        font-weight: 600;
        margin: 0 0 0.4rem 0;
        color: #1f1f1f;
    }

    .suggestion-region {
        font-family: 'Fraunces', Georgia, serif;
        font-size: 0.95rem;
        color: rgba(60, 60, 60, 0.65);
        margin: 0;
        letter-spacing: 0.02em;
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(14px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Title -------------------------------------------------------------------
st.markdown('<div class="search-title">Describe your dream holiday :)</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="search-subtitle">Three hand-picked destinations will appear below.</div>',
    unsafe_allow_html=True,
)

# --- Input -------------------------------------------------------------------
prompt = st.text_area(
    "Your holiday",
    value=st.session_state.get("search_prompt", ""),
    placeholder="e.g. A warm beach holiday with good nightlife and seafood...",
    height=140,
    label_visibility="collapsed",
)

col_left, col_center, col_right = st.columns([1, 1, 1])
with col_center:
    find = st.button("Find destinations", use_container_width=True)

# --- Suggestions -------------------------------------------------------------
if find:
    if not prompt.strip():
        st.warning("Tell us a little about your ideal holiday first.")
    else:
        st.session_state["search_prompt"] = prompt
        with st.spinner("Asking Gemini for ideas..."):
            destinations = [
                {k: v for k, v in row.items() if k not in ("lat", "lng")}
                for row in db.get_all_destinations()
            ]
            ids = route_destinations(prompt, destinations, st.secrets["GEMINI_API_KEY"])
            st.session_state["search_suggestion_ids"] = ids

suggestion_ids = st.session_state.get("search_suggestion_ids")

if suggestion_ids:
    cards_html = ['<div class="suggestion-grid">']
    for dest_id in suggestion_ids:
        dest = db.get_destination(int(dest_id))
        if not dest:
            continue
        name = dest["name"]
        region = dest["region"]
        cards_html.append(
            '<div class="suggestion-card">'
            f'<div class="suggestion-name">{name}</div>'
            f'<div class="suggestion-region">{region}</div>'
            '</div>'
        )
    cards_html.append('</div>')
    st.markdown("".join(cards_html), unsafe_allow_html=True)

    st.write("")  # spacer
    sel_left, sel_center, sel_right = st.columns([1, 1, 1])
    with sel_center:
        chosen = st.selectbox(
            "Pick a destination to explore on the dashboard",
            options=suggestion_ids,
            format_func=lambda i: db.get_destination(int(i))["name"],
        )
        if st.button("View dashboard", use_container_width=True):
            st.session_state["selected_destination_id"] = int(chosen)
            st.switch_page("pages/2_Dashboard.py")
