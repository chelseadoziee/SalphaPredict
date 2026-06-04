"""SalphaPredict Streamlit home page."""

from __future__ import annotations

import config
from streamlit_ui.components import feature_grid, render_html
from streamlit_ui.navigation import UPLOAD_PAGE, page_button
from streamlit_ui.theme import configure_page, render_footer

config.ensure_directories()
configure_page("Home")

render_html(
    '<section class="hero section-black hero-streamlit">'
    '<div class="hero-content">'
    '<p class="eyebrow">Salpha Energy</p>'
    '<h1 class="h1-large">Forecast Demand. Plan. Stock.</h1>'
    '<p class="lead">'
    "Upload your product sales file, see what sells most, what makes the most money, "
    "and plan stock with clearer numbers."
    "</p>"
    "</div>"
    "</section>"
)

page_button("Upload sales data", UPLOAD_PAGE, key="home_upload")

feature_grid(
    [
        ("Upload and clean", "Import Excel sales files and prepare them for analysis."),
        ("Sales insights", "Identify best-selling products, slow movers, and demand trends."),
        (
            "Smart Forecast",
            "Compare Trend, Recent Sales, Smooth Trend, and Pattern forecasts; "
            "the best method is chosen for you.",
        ),
        ("Stock recommendations", "Generate practical inventory guidance and trend alerts."),
    ]
)

render_footer()
