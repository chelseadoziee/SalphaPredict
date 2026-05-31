from __future__ import annotations

import streamlit as st

import config
from logic.recommendation_engine import generate_stock_advice_file
from streamlit_ui.charts import stock_advice_charts
from streamlit_ui.components import (
    chart_card,
    insight_summary,
    kpi_grid,
    page_header,
    priority_badge,
    render_html,
    render_table,
    section_card,
)
from streamlit_ui.session import require_cleaned_path
from streamlit_ui.theme import configure_page, render_footer

config.ensure_directories()
configure_page("Stock advice")
cleaned_path = require_cleaned_path()

advice = generate_stock_advice_file(cleaned_path)
if not advice.get("success"):
    st.error(advice.get("error", "Could not generate stock advice from the cleaned sales data."))
    st.stop()

summary = advice["summary"]

page_header(
    "Stock advice",
    f'Stock guidance from uploaded product data: <strong>{advice["source_file"]}</strong> '
    f'({advice["date_range"]["start"]} to {advice["date_range"]["end"]}).',
)

kpi_grid(
    [
        {"label": "Products covered", "value": summary["products_with_advice"]},
        {"label": "Priority restock", "value": summary["priority_restock_count"]},
        {"label": "Watch before restocking", "value": summary["watch_count"]},
        {"label": "Suggested units next month", "value": summary["total_suggested_units"]},
    ]
)

insight_summary("Stock insight", advice.get("stock_insight", []))

chart_card(
    "Suggested stock by product",
    "Recommended units to hold for next month, based on sales and forecast.",
)
stock_advice_charts(advice.get("charts", {}))

section_card(
    "Priority restock",
    "Top sellers and fast-moving products that should stay well stocked.",
    highlight=True,
)

priority_restock = advice.get("priority_restock", [])
if priority_restock:
    render_table(
        [
            "Product",
            "Last month sold",
            "Next month forecast",
            "Suggested stock",
            "Advice",
        ],
        [
            [
                row["product"],
                row["last_month_sold"],
                row["next_month_forecast"] if row.get("next_month_forecast") is not None else "—",
                row["suggested_stock"],
                priority_badge(row["advice_label"], row["priority"]),
            ]
            for row in priority_restock
        ],
    )
else:
    render_html('<p class="muted">No priority restock items were flagged in the current data.</p>')

watch_list = advice.get("watch_list", [])
if watch_list:
    section_card(
        "Watch before restocking",
        "Products where demand is falling or profit is weak — restock carefully.",
    )
    render_table(
        ["Product", "Last month sold", "Direction", "Suggested stock", "Advice"],
        [
            [
                row["product"],
                row["last_month_sold"],
                row["trend_label"],
                row["suggested_stock"],
                priority_badge(row["advice_label"], row["priority"]),
            ]
            for row in watch_list
        ],
    )

section_card(
    "All product stock advice",
    "Full list of products with suggested stock levels and reasons.",
)

render_table(
    [
        "Product",
        "Total sold",
        "Avg sold per month",
        "Next month forecast",
        "Suggested stock",
        "Advice",
        "Why",
    ],
    [
        [
            row["product"],
            row["total_sold"],
            row["avg_monthly_sold"],
            row["next_month_forecast"] if row.get("next_month_forecast") is not None else "—",
            row["suggested_stock"],
            priority_badge(row["advice_label"], row["priority"]),
            row["reason"],
        ]
        for row in advice.get("recommendations", [])
    ],
)

render_footer()
