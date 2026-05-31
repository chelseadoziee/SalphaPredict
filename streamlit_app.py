"""SalphaPredict Streamlit entry point."""

from __future__ import annotations

import streamlit as st

import config
from streamlit_ui.navigation import register_app_pages
from streamlit_ui.theme import init_app

config.ensure_directories()
init_app()

pages = register_app_pages()
pg = st.navigation(
    [
        pages["home"],
        pages["upload"],
        pages["sales"],
        pages["forecast"],
        pages["profit_loss"],
        pages["stock_advice"],
    ]
)
pg.run()
