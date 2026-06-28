"""Holiday Planner — single-page entry point.

Acts as a tiny router: the Home page *is* the search page. When a user picks a
destination we flip ``st.session_state["view"]`` to ``"dashboard"`` and render
the dashboard in place — no extra Streamlit pages, no sidebar navigation.
Heavy lifting (fetching, caching, LLM calls) lives in ``src/`` behind DuckDB.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Holiday Planner",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import theme
from src import database as db
from views import dashboard_view, search_view

db.init_db()
theme.inject_global_css()

ss = st.session_state
ss.setdefault("view", "search")
ss.setdefault("suggestion_ids", [])
ss.setdefault("search_prompt", "")
ss.setdefault("selected_destination_id", None)
ss.setdefault("active_tab", "see")

if ss["view"] == "dashboard" and ss["selected_destination_id"] is not None:
    dashboard_view.render()
else:
    search_view.render()
