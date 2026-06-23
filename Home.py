import streamlit as st

from src import database as db

st.set_page_config(page_title="Holiday Planner", layout="wide")

db.init_db()

st.title("Holiday Planner")
st.write(
    "Describe your ideal holiday, pick a destination, and explore weather, "
    "venues, and travel tips on the dashboard."
)
