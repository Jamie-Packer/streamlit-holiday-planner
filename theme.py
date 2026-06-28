"""Shared UI theming for the Holiday Planner Streamlit app.

This is the *UI layer* (it imports Streamlit) — kept out of `src/`, which must
stay Streamlit-free per the architecture rule. Holds the global CSS, the serif
typography, and small helpers for turning destination images into inline data
URIs (so we can use them as CSS backgrounds in custom HTML cards without
depending on Pillow).
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

_IMAGE_DIR = Path(__file__).resolve().parent / "images" / "destinations"

# A neutral warm gradient used wherever a destination image is missing.
_FALLBACK_GRADIENT = "linear-gradient(135deg, #d9c7b1 0%, #b89274 100%)"


_GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap');

:root {
    --hp-serif-display: 'Fraunces', Georgia, 'Times New Roman', serif;
    --hp-serif-body: 'Source Serif 4', Georgia, serif;
    --hp-ink: #2B2622;
    --hp-muted: rgba(43, 38, 34, 0.62);
    --hp-accent: #C2683A;
    --hp-card-radius: 22px;
}

html, body, [data-testid="stAppViewContainer"], .stApp {
    font-family: var(--hp-serif-body);
    color: var(--hp-ink);
}

h1, h2, h3, h4, h5 {
    font-family: var(--hp-serif-display) !important;
    letter-spacing: -0.015em;
    font-weight: 600;
}

/* Tighten the default top padding so content sits higher. */
.block-container {
    padding-top: 2.2rem;
    padding-bottom: 4rem;
    max-width: 1180px;
}

/* Buttons: pill-shaped, soft, with a gentle lift on hover. */
.stButton > button {
    border-radius: 999px;
    border: 1px solid rgba(43, 38, 34, 0.14);
    padding: 0.5rem 1.25rem;
    font-family: var(--hp-serif-display);
    font-weight: 500;
    transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(43, 38, 34, 0.12);
    border-color: rgba(43, 38, 34, 0.22);
}
.stButton > button[kind="primary"] {
    background: var(--hp-accent);
    border-color: var(--hp-accent);
    color: #fff;
}

/* Search input styled as a rounded "chat bar". */
.stTextInput > div > div > input,
.stTextArea textarea {
    border-radius: 16px !important;
    font-family: var(--hp-serif-body);
    font-size: 1.05rem;
}

/* ---- Search view -------------------------------------------------------- */
.hp-search-title {
    font-family: var(--hp-serif-display);
    font-size: 3.2rem;
    font-weight: 600;
    text-align: center;
    margin: 0 0 0.4rem 0;
    line-height: 1.05;
}
.hp-search-sub {
    font-family: var(--hp-serif-body);
    text-align: center;
    color: var(--hp-muted);
    font-size: 1.1rem;
    margin-bottom: 1.4rem;
}
.hp-spacer-lg { height: 9vh; }

/* ---- Destination cards (search results) -------------------------------- */
.hp-card {
    border-radius: var(--hp-card-radius);
    overflow: hidden;
    background: #fff;
    border: 1px solid rgba(43, 38, 34, 0.07);
    box-shadow: 0 10px 30px rgba(43, 38, 34, 0.10);
    animation: hpFadeInUp 0.55s ease both;
}
.hp-card-img {
    height: 200px;
    background-size: cover;
    background-position: center;
}
.hp-card-body { padding: 1rem 1.15rem 1.1rem 1.15rem; }
.hp-card-name {
    font-family: var(--hp-serif-display);
    font-size: 1.45rem;
    font-weight: 600;
    margin: 0;
    line-height: 1.15;
}
.hp-card-country {
    font-family: var(--hp-serif-body);
    font-size: 1rem;
    color: var(--hp-ink);
    margin: 0.15rem 0 0 0;
}
.hp-card-region {
    font-family: var(--hp-serif-body);
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--hp-muted);
    margin: 0.45rem 0 0 0;
}

/* ---- Dashboard hero ----------------------------------------------------- */
.hp-hero {
    position: relative;
    height: 320px;
    border-radius: var(--hp-card-radius);
    overflow: hidden;
    background-size: cover;
    background-position: center;
    box-shadow: 0 14px 36px rgba(43, 38, 34, 0.18);
    margin-bottom: 0.5rem;
    animation: hpFadeInUp 0.5s ease both;
}
.hp-hero::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,0) 35%, rgba(0,0,0,0.62) 100%);
}
.hp-hero-content {
    position: absolute;
    left: 0; bottom: 0;
    padding: 1.6rem 2rem;
    z-index: 2;
    color: #fff;
}
.hp-hero-name {
    font-family: var(--hp-serif-display);
    font-size: 2.8rem;
    font-weight: 700;
    margin: 0;
    line-height: 1;
    text-shadow: 0 2px 14px rgba(0,0,0,0.35);
}
.hp-hero-meta {
    font-family: var(--hp-serif-body);
    font-size: 1.1rem;
    margin: 0.4rem 0 0 0;
    opacity: 0.95;
    text-shadow: 0 1px 8px rgba(0,0,0,0.35);
}
.hp-section-title {
    font-family: var(--hp-serif-display);
    font-size: 1.5rem;
    font-weight: 600;
    margin: 1.6rem 0 0.6rem 0;
}

@keyframes hpFadeInUp {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
}
</style>
"""


def inject_global_css() -> None:
    """Inject the global stylesheet. Call once per script run, after page config."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def image_data_uri(destination_id: int) -> str | None:
    """Return a base64 ``data:`` URI for a destination's WebP image, or None.

    Encoding to a data URI lets us use the image as a CSS ``background-image``
    in custom HTML (hero banners, cards) and renders WebP natively in the
    browser — no Pillow dependency required.
    """
    path = _IMAGE_DIR / f"{destination_id}.webp"
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/webp;base64,{encoded}"


def image_css_value(destination_id: int) -> str:
    """Return a CSS ``background-image`` value: the image URL or a fallback gradient."""
    uri = image_data_uri(destination_id)
    if uri is None:
        return _FALLBACK_GRADIENT
    return f"url('{uri}')"
