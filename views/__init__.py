"""Streamlit UI views for the Holiday Planner single-page app.

Lives outside ``pages/`` on purpose: Streamlit auto-registers ``pages/`` files
as navigable pages, but we drive navigation ourselves via ``st.session_state``
(search view <-> dashboard view) from ``Home.py``.
"""
