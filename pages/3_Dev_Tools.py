"""Hidden-ish cache hygiene page (sidebar nav is off in config.toml).

Reach via the Streamlit multipage URL, e.g. ``/Dev_Tools``. Not part of the
recruiter-facing search → dashboard flow.
"""

from __future__ import annotations

import streamlit as st

from src import database as db

st.set_page_config(page_title="Dev Tools", page_icon="🧰", layout="centered")
st.title("Dev Tools")
st.caption("Local / deploy hygiene — not linked from the main app.")

db.init_db()

counts = db.spoke_cache_counts()
st.subheader("Spoke cache counts")
st.dataframe(
    [{"table": table, "rows": counts[table]} for table in db.SPOKE_TABLES],
    hide_index=True,
    width="stretch",
)
st.write(f"Destinations hub: **{len(db.get_all_destinations())}** rows")

st.divider()
st.subheader("Purge spoke caches")
st.markdown(
    "Deletes all rows from weather, places, google_places, wikivoyage, fcdo, "
    "and summaries. Leaves `destinations` alone. Use before committing "
    "`data/planner.db` so Community Cloud cold-starts with a fresh cache."
)

if st.button("Purge all spoke caches", type="primary"):
    cleared = db.purge_spoke_caches()
    # Drop in-process Streamlit memoisation of dashboard loaders so the next
    # visit actually re-hits DuckDB / fetchers instead of a stale @st.cache_data hit.
    st.cache_data.clear()
    st.success(
        "Purged: "
        + ", ".join(f"{table}={n}" for table, n in cleared.items())
    )
    st.rerun()
