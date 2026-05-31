from __future__ import annotations

import streamlit as st

import config
from logic.sales_analyser import analyse_sales_file
from streamlit_ui.charts import dashboard_charts
from streamlit_ui.components import (
    chart_card,
    insight_summary,
    kpi_grid,
    money_cell,
    page_header,
    render_html,
    render_table,
    section_card,
)
from streamlit_ui.session import require_cleaned_path
from streamlit_ui.theme import configure_page, render_footer

config.ensure_directories()
configure_page("Sales")
cleaned_path = require_cleaned_path()

analysis = analyse_sales_file(cleaned_path)
if not analysis.get("success"):
    st.error(analysis.get("error", "Could not analyse the cleaned sales data."))
    st.stop()

summary = analysis["summary"]
trend = analysis["demand_trend"]

page_header(
    "Salpha Product Insights",
    f'Summary from uploaded product data: <strong>{analysis["source_file"]}</strong> '
    f'({analysis["date_range"]["start"]} to {analysis["date_range"]["end"]}).',
)

kpi_grid(
    [
        {"label": "Total products sold", "value": f'{summary["total_units"]:,}'},
        {
            "label": "Total money made",
            "value": summary["total_revenue"],
            "money": True,
        },
        {"label": "Products listed", "value": summary["unique_products"]},
        {"label": "Average sold per day", "value": summary["avg_daily_units"]},
        {
            "label": "Sales direction",
            "value": trend["label"],
            "trend_class": trend["direction"],
            "sub": (
                f'{trend["change_pct"]}% compared to last month'
                if trend.get("change_pct") is not None
                else None
            ),
        },
        {"label": "Top 3 share of products sold", "value": f'{summary["top_three_share_pct"]}%'},
    ]
)

insight_summary("Key insight", analysis.get("key_insight", []))

chart_specs = [
    ("Monthly products sold", "Shows how many products were sold each month."),
]
if summary.get("total_revenue") is not None:
    chart_specs.append(("Monthly money made", "Shows how much money was made each month."))
chart_specs.extend(
    [
        ("Most popular products", "Shows which products were sold the most."),
    ]
)
if analysis.get("revenue_by_product"):
    chart_specs.append(("Money made by product", "Shows which products brought in the most money."))

cols = st.columns(2)
for index, (title, caption) in enumerate(chart_specs):
    with cols[index % 2]:
        chart_card(title, caption)

charts = analysis.get("charts", {})
dashboard_charts(charts)

section_card(
    "Product overview",
    "All products in one place — how many were sold and how much money each one made.",
)

has_revenue = summary.get("total_revenue") is not None
headers = ["Product", "Sold", "Share of products sold"]
if has_revenue:
    headers.extend(["Money made", "Share of money made"])

rows = []
for row in analysis.get("product_overview", []):
    cells = [
        row["product"],
        row["quantity"],
        f'{row["quantity_share_pct"]}%',
    ]
    if has_revenue:
        cells.extend(
            [
                money_cell(row.get("revenue")),
                (
                    f'{row["revenue_share_pct"]}%'
                    if row.get("revenue_share_pct") is not None
                    else "—"
                ),
            ]
        )
    rows.append(cells)
render_table(headers, rows)

section_card(
    "High-value products",
    "These products made strong money, even when some sold fewer units.",
    highlight=True,
)

high_value = analysis.get("high_value_products", [])
if high_value:
    render_table(
        ["Product", "Sold", "Money made", "Share of money made"],
        [
            [
                row["product"],
                row["quantity"],
                money_cell(row["revenue"]),
                f'{row["revenue_share_pct"]}%',
            ]
            for row in high_value
        ],
    )
else:
    render_html('<p class="muted">No high-value products were identified in the current data.</p>')

render_footer()
