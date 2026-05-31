from __future__ import annotations

import streamlit as st

HOME_PAGE = "home"
UPLOAD_PAGE = "upload"
SALES_PAGE = "sales"
FORECAST_PAGE = "forecast"
PROFIT_LOSS_PAGE = "profit_loss"
STOCK_ADVICE_PAGE = "stock_advice"

_SESSION_KEY = "_app_pages"


def register_app_pages() -> dict[str, object]:
    """Create Streamlit page objects and cache them for custom navigation."""
    pages = {
        HOME_PAGE: st.Page("pages/0_Home.py", title="Home", default=True),
        UPLOAD_PAGE: st.Page("pages/1_Upload.py"),
        SALES_PAGE: st.Page("pages/2_Sales.py"),
        FORECAST_PAGE: st.Page("pages/3_Forecast.py"),
        PROFIT_LOSS_PAGE: st.Page("pages/4_Profit_and_Loss.py"),
        STOCK_ADVICE_PAGE: st.Page("pages/5_Stock_Advice.py"),
    }
    st.session_state[_SESSION_KEY] = pages
    return pages


def _get_page(page_key: str):
    pages = st.session_state.get(_SESSION_KEY)
    if not pages:
        return None
    return pages.get(page_key)


def switch_to_page(page_key: str) -> None:
    """Navigate to another app page."""
    page = _get_page(page_key)
    if page is None:
        st.error(f"Could not find page: {page_key}")
        return
    st.switch_page(page)


def page_button(label: str, page_key: str, *, key: str | None = None) -> None:
    """Render a button that navigates to another page."""
    if st.button(label, key=key, use_container_width=False):
        switch_to_page(page_key)
