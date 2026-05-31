from __future__ import annotations

from pathlib import Path

import streamlit as st

import config
from streamlit_ui.components import render_html

CSS_PATH = config.BASE_DIR / "static" / "css" / "styles.css"

STREAMLIT_OVERRIDES = """
<style>
    .stApp {
        background-color: #f0ece9;
    }

    [data-testid="stSidebar"] {
        background-color: #000000;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span {
        color: rgba(255, 255, 255, 0.88);
    }

    [data-testid="stSidebarNav"] a {
        color: rgba(255, 255, 255, 0.88) !important;
    }

    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background: #ffdd00 !important;
        color: #000000 !important;
    }

    div[data-testid="stFileUploader"] section {
        background: #ffffff;
        border: 1px solid #ddd8d4;
        border-radius: 0;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.08);
        padding: 1rem;
    }

    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #ddd8d4;
        border-top: 3px solid #ffdd00;
        padding: 1rem;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.08);
    }

    .stButton > button {
        background: #ffdd00;
        color: #000000;
        border: none;
        border-radius: 0;
        font-weight: 700;
    }

    .stButton > button:hover {
        background: #ffe94d;
        color: #000000;
        border: none;
    }

    div[data-testid="stSelectbox"] > div > div {
        border-radius: 0;
    }

    header[data-testid="stHeader"] {
        background: rgba(0, 0, 0, 0);
    }

    .block-container {
        padding-top: 1rem;
        max-width: 1100px;
    }

    .salpha-brand-bar {
        background: #000000;
        color: #ffffff;
        padding: 1rem 0;
        margin: -1rem calc(50% - 50vw) 1.5rem;
        width: 100vw;
    }

    .salpha-brand-inner {
        width: min(1100px, 92%);
        margin: 0 auto;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .hero-streamlit {
        border-radius: 0;
        padding: clamp(3rem, 8vw, 6rem) 1.5rem;
        margin: 0 calc(50% - 50vw) 2rem;
        width: 100vw;
        max-width: 100vw;
        background: #000000;
        color: #ffffff;
        text-align: center;
    }

    .hero-streamlit .hero-content {
        max-width: 680px;
        margin: 0 auto;
    }

    .hero-streamlit .h1-large {
        color: #ffffff;
        margin: 0.75rem 0 1.25rem;
    }

    .hero-streamlit .lead {
        max-width: 52ch;
        margin: 0 auto 1.75rem;
        color: rgba(255, 255, 255, 0.88);
    }

    .streamlit-chart-card {
        margin-bottom: 0.5rem;
    }
</style>
"""


def load_brand_css() -> str:
    if CSS_PATH.exists():
        return CSS_PATH.read_text(encoding="utf-8")
    return ""


def apply_theme() -> None:
    st.markdown(f"<style>{load_brand_css()}</style>", unsafe_allow_html=True)
    st.markdown(STREAMLIT_OVERRIDES, unsafe_allow_html=True)


def render_brand_bar() -> None:
    render_html(
        '<div class="salpha-brand-bar">'
        '<div class="salpha-brand-inner">'
        '<span class="brand-mark">S</span>'
        '<span class="brand-text">'
        "<strong>SalphaPredict</strong>"
        "<small>Salpha Energy</small>"
        "</span>"
        "</div>"
        "</div>"
    )


def render_footer() -> None:
    render_html(
        '<footer class="site-footer" style="margin: 2rem calc(50% - 50vw) 0; width: 100vw;">'
        '<div class="container">'
        "<p>SalphaPredict &mdash; Demand intelligence for Salpha Energy</p>"
        "</div>"
        "</footer>"
    )


def init_app() -> None:
    """Configure the Streamlit app once from the entry script."""
    st.set_page_config(
        page_title="SalphaPredict",
        page_icon="S",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()


def configure_page(title: str) -> None:
    render_brand_bar()
