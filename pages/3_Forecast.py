from __future__ import annotations

import streamlit as st

import config
from logic.forecasting_engine import forecast_sales_file
from streamlit_ui.charts import forecast_charts
from streamlit_ui.components import (
    action_priority,
    advice_list,
    chart_card,
    insight_summary,
    kpi_grid,
    money_cell,
    page_header,
    priority_badge,
    render_html,
    render_table,
    section_card,
)
from streamlit_ui.session import require_cleaned_path
from streamlit_ui.theme import configure_page, render_footer

config.ensure_directories()
configure_page("Forecast")
cleaned_path = require_cleaned_path()

section_card(
    "Forecast settings",
    "Choose how far ahead to look. Product filter applies to all products for now.",
)

period_options = {1: "Next month", 3: "Next 3 months", 6: "Next 6 months"}
period = st.selectbox(
    "Forecast period",
    options=list(period_options.keys()),
    format_func=lambda value: period_options[value],
    index=0,
)

forecast_report = forecast_sales_file(cleaned_path, forecast_periods=period)
if not forecast_report.get("success"):
    st.error(forecast_report.get("error", "Could not forecast from the cleaned sales data."))
    st.stop()

st.selectbox(
    "Product filter",
    options=[forecast_report["controls"]["product_filter"]],
    disabled=True,
)

summary = forecast_report["summary"]

page_header(
    "Sales Forecast",
    f'A simple look at what products may sell next based on uploaded sales data. '
    f'Source: <strong>{forecast_report["source_file"]}</strong> '
    f'({forecast_report["history_range"]["start"]} to {forecast_report["history_range"]["end"]}).',
)

kpi_grid(
    [
        {
            "label": "Expected products sold",
            "value": summary["expected_products_sold"],
            "sub": forecast_report["forecast_period_label"],
        },
        {
            "label": "Expected money made",
            "value": summary["expected_money_made"],
            "money": True,
        },
        {
            "label": "Expected profit",
            "value": (
                summary["expected_profit"]
                if summary.get("has_profit") and summary.get("expected_profit") is not None
                else "—"
            ),
            "money": summary.get("has_profit") and summary.get("expected_profit") is not None,
        },
        {"label": "Restock alerts", "value": summary["restock_alerts"]},
        {
            "label": "Top forecast product",
            "value": summary["top_forecast_product"],
            "text_value": True,
        },
        {
            "label": "Forecast confidence",
            "value": summary["forecast_confidence"],
            "sub": summary.get("forecast_confidence_detail"),
        },
    ]
)

insight_summary("What this could mean", forecast_report.get("what_this_means", []))

charts = forecast_report.get("charts", {})
chart_specs = [("Expected products sold", "Past monthly sales and what may happen next.")]
if charts.get("money_made"):
    chart_specs.append(("Expected money made", "Past monthly money made and what may happen next."))
if charts.get("profit"):
    chart_specs.append(("Expected profit", "Past monthly profit and what may happen next."))
chart_specs.append(
    ("Expected sold by product", "Which products may sell the most in the forecast period.")
)
if charts.get("product_money"):
    chart_specs.append(
        ("Expected money made by product", "Which products may bring in the most money.")
    )
if charts.get("product_profit"):
    chart_specs.append(
        ("Expected profit by product", "Which products may make the most profit.")
    )

cols = st.columns(2)
for index, (title, caption) in enumerate(chart_specs):
    with cols[index % 2]:
        chart_card(title, caption)

forecast_charts(charts)

section_card(
    "Product forecast",
    f'What each product may do in {forecast_report["forecast_period_label"].lower()}.',
)

render_table(
    ["Product", "Expected sold", "Expected money made", "Expected profit", "Suggested action"],
    [
        [
            row["product"],
            row["expected_sold"],
            money_cell(row.get("expected_money_made"), compact=True),
            money_cell(row.get("expected_profit"), compact=True),
            priority_badge(row["suggested_action"], action_priority(row["suggested_action"])),
        ]
        for row in forecast_report.get("forecast_table", [])
    ],
)

stock_advice = forecast_report.get("stock_advice", {})
col1, col2, col3 = st.columns(3)
with col1:
    render_html(
        '<article class="dashboard-card stock-advice-card">'
        "<h2>Restock soon</h2>"
        '<p class="muted chart-caption">Fast sellers that may need regular restocking.</p>'
        "</article>"
    )
    if stock_advice.get("restock_soon"):
        advice_list(
            [
                f'{row["product"]} — {row["suggested_action"]} (about {row["expected_sold"]} units)'
                for row in stock_advice["restock_soon"]
            ]
        )
    else:
        render_html('<p class="muted">No urgent restock alerts in this forecast.</p>')
with col2:
    render_html(
        '<article class="dashboard-card stock-advice-card">'
        "<h2>Track closely</h2>"
        '<p class="muted chart-caption">Products with rising demand worth watching.</p>'
        "</article>"
    )
    if stock_advice.get("track_closely"):
        advice_list(
            [
                f'{row["product"]} — {row["suggested_action"]} (about {row["expected_sold"]} units)'
                for row in stock_advice["track_closely"]
            ]
        )
    else:
        render_html('<p class="muted">No products flagged to track closely.</p>')
with col3:
    render_html(
        '<article class="dashboard-card stock-advice-card">'
        "<h2>Watch list</h2>"
        '<p class="muted chart-caption">Products where demand may fall or profit is weak.</p>'
        "</article>"
    )
    if stock_advice.get("watch_list"):
        advice_list(
            [
                f'{row["product"]} — {row["suggested_action"]}'
                for row in stock_advice["watch_list"]
            ]
        )
    else:
        render_html('<p class="muted">No products on the watch list.</p>')

render_footer()
