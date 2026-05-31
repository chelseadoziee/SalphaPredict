from __future__ import annotations

import streamlit as st

import config
from logic.profit_analyser import analyse_profit_file
from streamlit_ui.charts import profit_loss_charts
from streamlit_ui.components import (
    chart_card,
    insight_summary,
    kpi_grid,
    money_cell,
    notice_card,
    page_header,
    render_html,
    render_table,
    section_card,
)
from streamlit_ui.session import require_cleaned_path
from streamlit_ui.theme import configure_page, render_footer

config.ensure_directories()
configure_page("Profit & loss")
cleaned_path = require_cleaned_path()

analysis = analyse_profit_file(cleaned_path)
if not analysis.get("success"):
    st.error(analysis.get("error", "Could not analyse profit from the cleaned sales data."))
    st.stop()

summary = analysis["summary"]

page_header(
    "Profit & loss",
    f'Profit and loss summary from uploaded product data: <strong>{analysis["source_file"]}</strong> '
    f'({analysis["date_range"]["start"]} to {analysis["date_range"]["end"]}).',
)

if analysis.get("mock_cost_disclaimer"):
    notice_card(analysis["mock_cost_disclaimer"])

kpi_grid(
    [
        {"label": "Total money made", "value": summary["total_money_made"], "money": True},
        {"label": "Total cost", "value": summary["total_cost"], "money": True},
        {"label": "Gross profit", "value": summary["total_gross_profit"], "money": True},
        {
            "label": "Total loss",
            "value": summary["total_loss"],
            "money": True,
            "trend_class": "down",
        },
        {"label": "Net result", "value": summary["net_result"], "money": True},
        {"label": "Loss-making products", "value": summary["loss_making_products"]},
    ]
)

insight_summary("Profit & loss insight", analysis.get("profit_insight", []))

charts = analysis.get("charts", {})
chart_specs = [
    ("Monthly profit and loss", "Gross profit and loss each month, based on money made vs total cost."),
    ("Monthly money made vs cost", "Compares money made against total cost each month."),
    ("Profit by product", "Products with the highest gross profit."),
]
if charts.get("loss_by_product"):
    chart_specs.append(
        ("Loss by product", "Products where cost was higher than money made.")
    )

cols = st.columns(2)
for index, (title, caption) in enumerate(chart_specs):
    with cols[index % 2]:
        chart_card(title, caption)

profit_loss_charts(charts)

section_card(
    "Product profit & loss overview",
    "All products with profit data — gross profit, loss, and net result for each one.",
)

render_table(
    [
        "Product",
        "Money made",
        "Total cost",
        "Gross profit",
        "Loss",
        "Net result",
        "Profit margin",
    ],
    [
        [
            row["product"],
            money_cell(row["money_made"]),
            money_cell(row["total_cost"]),
            money_cell(row["gross_profit"]) if row.get("gross_profit") else "—",
            money_cell(row["loss"]) if row.get("loss") else "—",
            money_cell(row["net_result"]),
            f'{row["profit_margin_pct"]}%',
        ]
        for row in analysis.get("product_profit_overview", [])
    ],
)

loss_making = analysis.get("loss_making_products", [])
if loss_making:
    section_card(
        "Loss-making products",
        "Products where total cost was higher than money made — review pricing or costs for these.",
        highlight=True,
    )
    render_table(
        ["Product", "Money made", "Total cost", "Loss", "Share of total loss"],
        [
            [
                row["product"],
                money_cell(row["money_made"]),
                money_cell(row["total_cost"]),
                money_cell(row["loss"]),
                f'{row["loss_share_pct"]}%',
            ]
            for row in loss_making
        ],
    )

section_card(
    "Highest margin products",
    "Products with the strongest profit margin — useful when comparing value per sale.",
)

render_table(
    ["Product", "Money made", "Net result", "Profit margin"],
    [
        [
            row["product"],
            money_cell(row["money_made"]),
            money_cell(row["net_result"]),
            f'{row["profit_margin_pct"]}%',
        ]
        for row in analysis.get("highest_margin_products", [])
    ],
)

render_footer()
