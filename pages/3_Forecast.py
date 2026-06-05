from __future__ import annotations

import streamlit as st

import config
from logic.forecasting_engine import ALL_PRODUCTS_LABEL, forecast_sales_file, list_forecast_products
from streamlit_ui.charts import render_forecast_chart
from streamlit_ui.components import (
    action_priority,
    advice_list,
    chart_card,
    insight_summary,
    kpi_grid,
    method_comparison_panel,
    money_cell,
    notice_card,
    page_header,
    priority_badge,
    render_html,
    render_table,
    section_card,
    smart_forecast_panel,
)
from streamlit_ui.session import require_cleaned_path
from streamlit_ui.theme import configure_page, render_footer

config.ensure_directories()
configure_page("Forecast")
cleaned_path = require_cleaned_path()

product_list_result = list_forecast_products(cleaned_path)
if not product_list_result.get("success"):
    st.error(product_list_result.get("error", "Could not load products for forecasting."))
    st.stop()

product_names = product_list_result.get("products", [])
filter_options = [("", ALL_PRODUCTS_LABEL)] + [(name, name) for name in product_names]

section_card(
    "Forecast settings",
    "Choose how far ahead to look and optionally focus on one product.",
)

settings_col1, settings_col2 = st.columns(2)
with settings_col1:
    period_options = {1: "Next month", 3: "Next 3 months", 6: "Next 6 months"}
    period = st.selectbox(
        "Forecast period",
        options=list(period_options.keys()),
        format_func=lambda value: period_options[value],
        index=0,
    )
with settings_col2:
    selected_filter = st.selectbox(
        "Product filter",
        options=filter_options,
        format_func=lambda item: item[1],
        index=0,
    )

selected_product = selected_filter[0] or None
product_caption = (
    f"Viewing {selected_product} only."
    if selected_product
    else f"Viewing {ALL_PRODUCTS_LABEL.lower()} combined."
)
render_html(f'<p class="muted chart-caption">{product_caption}</p>')

forecast_report = forecast_sales_file(
    cleaned_path,
    forecast_periods=period,
    product=selected_product,
)
if not forecast_report.get("success"):
    st.error(forecast_report.get("error", "Could not forecast from the cleaned sales data."))
    st.stop()

page_header(
    "Sales Forecast",
    f'See what may sell next. SalphaPredict compares forecast methods on your sales history '
    f'and uses the most accurate one automatically. '
    f'Source: <strong>{forecast_report["source_file"]}</strong> '
    f'({forecast_report["history_range"]["start"]} to {forecast_report["history_range"]["end"]}).',
)

FORECAST_INSIGHT_TITLE = "What the Forecast Is Telling You"
FORECAST_INSIGHT_CAPTION = (
    "A plain language summary of the key things this forecast suggests "
    "for your stock and sales planning."
)

if forecast_report.get("is_smart_forecast"):
    smart_forecast_panel(forecast_report)
    comparison = forecast_report.get("method_comparison")
    if comparison:
        method_comparison_panel(comparison)
    else:
        notice_card(
            "Method comparison appears after at least 7 months of sales history "
            "(4 months to train, 3 months to test). Until then, Smart Forecast uses "
            "Trend Forecast as a reliable default."
        )

is_product_journey = forecast_report.get("view_mode") == "product_journey"
focus = forecast_report.get("product_focus")
chosen_label = forecast_report.get("chosen_method_display_name")

if is_product_journey and focus:
    kpi_grid(
        [
            {
                "label": "Expected products sold",
                "value": focus["expected_products_sold"],
                "sub": forecast_report["forecast_period_label"],
            },
            {
                "label": "Expected money made",
                "value": focus["expected_money_made"],
                "money": True,
            },
            {
                "label": "Expected profit",
                "value": (
                    focus["expected_profit"]
                    if focus.get("has_profit") and focus.get("expected_profit") is not None
                    else "N/A"
                ),
                "money": focus.get("has_profit") and focus.get("expected_profit") is not None,
            },
            {
                "label": "Forecast confidence",
                "value": focus["forecast_confidence"],
                "sub": focus.get("forecast_confidence_detail"),
            },
            {
                "label": "Restock status",
                "value": focus["restock_status"],
                "text_value": True,
            },
            {
                "label": "Trend direction",
                "value": focus["trend_direction"],
                "text_value": True,
            },
        ]
    )

    journey_caption = (
        f'Past sales leading into what is expected next for <strong>{focus["product"]}</strong>. '
        f'The dotted line shows where the forecast begins.'
    )
    if chosen_label:
        journey_caption += (
            f' Smart Forecast is using <strong>{chosen_label}</strong>.'
        )
    chart_card("Sales Timeline", journey_caption)
    render_forecast_chart(forecast_report.get("charts", {}), "journey_line")

    col1, col2 = st.columns(2)
    with col1:
        section_card(
            "Revenue Estimate",
            f"Total revenue expected for {focus['product']} over the selected period.",
        )
        if focus.get("expected_money_made") is not None:
            render_html(
                f'<p class="journey-summary-value kpi-value-money">'
                f'{money_cell(focus["expected_money_made"], compact=True)}</p>'
                f'<p class="summary-text">Last month sold {focus["last_month_sold"]} units. '
                f'Next month may reach about {focus["next_month_forecast"]} units.</p>'
            )
        else:
            render_html('<p class="muted">Revenue forecast is not available for this file.</p>')
    with col2:
        section_card(
            "Profit Estimate",
            f"How much profit {focus['product']} is expected to generate this period.",
        )
        if focus.get("has_profit") and focus.get("expected_profit") is not None:
            render_html(
                f'<p class="journey-summary-value kpi-value-money">'
                f'{money_cell(focus["expected_profit"], compact=True)}</p>'
                f'<p class="summary-text">Use this alongside the profit and loss page when reviewing margins.</p>'
            )
        else:
            render_html('<p class="muted">Profit forecast is not available for this file.</p>')

    section_card("Restock recommendation", focus["restock_recommendation"])
    render_html(
        f'<p class="muted chart-caption">Suggested action: {focus["suggested_action"]}</p>'
    )

    insight_summary(
        FORECAST_INSIGHT_TITLE,
        forecast_report.get("what_this_means", []),
        caption=FORECAST_INSIGHT_CAPTION,
    )
else:
    summary = forecast_report["summary"]
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
                    else "N/A"
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

    insight_summary(
        FORECAST_INSIGHT_TITLE,
        forecast_report.get("what_this_means", []),
        caption=FORECAST_INSIGHT_CAPTION,
    )

    charts = forecast_report.get("charts", {})
    chart_specs: list[tuple[str, str, str]] = [
        (
            "Sales Forecast",
            "How many units were sold each month, plus what is expected ahead.",
            "products_sold",
        )
    ]
    if charts.get("money_made"):
        chart_specs.append(
            (
                "Revenue Forecast",
                "Monthly revenue so far, with an estimate of what is coming next.",
                "money_made",
            )
        )
    if charts.get("profit"):
        chart_specs.append(
            (
                "Profit Forecast",
                "How much profit was made each month and what to expect going forward.",
                "profit",
            )
        )
    chart_specs.append(
        (
            "Top Products by Units",
            "The products forecast to sell the most next period.",
            "product_units",
        )
    )
    if charts.get("product_money"):
        chart_specs.append(
            (
                "Top Products by Revenue",
                "The products expected to bring in the most money.",
                "product_money",
            )
        )
    if charts.get("product_profit"):
        chart_specs.append(
            (
                "Top Products by Profit",
                "The products likely to deliver the strongest profit.",
                "product_profit",
            )
        )

    cols = st.columns(2)
    for index, (title, caption, chart_key) in enumerate(chart_specs):
        with cols[index % 2]:
            chart_card(title, caption)
            render_forecast_chart(charts, chart_key)

    section_card(
        "Product by Product Forecast",
        "Units, revenue, and profit estimates for each product, with a suggested stock action.",
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
            "<h2>Restock Soon</h2>"
            '<p class="muted chart-caption">Fast moving products that will likely need topping up before the period ends.</p>'
            "</article>"
        )
        if stock_advice.get("restock_soon"):
            advice_list(
                [
                    f'{row["product"]}: {row["suggested_action"]} (about {row["expected_sold"]} units)'
                    for row in stock_advice["restock_soon"]
                ]
            )
        else:
            render_html('<p class="muted">No urgent restock alerts in this forecast.</p>')
    with col2:
        render_html(
            '<article class="dashboard-card stock-advice-card">'
            "<h2>Rising Demand</h2>"
            '<p class="muted chart-caption">Products with growing sales that are worth keeping a close eye on.</p>'
            "</article>"
        )
        if stock_advice.get("track_closely"):
            advice_list(
                [
                    f'{row["product"]}: {row["suggested_action"]} (about {row["expected_sold"]} units)'
                    for row in stock_advice["track_closely"]
                ]
            )
        else:
            render_html('<p class="muted">No products flagged to track closely.</p>')
    with col3:
        render_html(
            '<article class="dashboard-card stock-advice-card">'
            "<h2>Needs Attention</h2>"
            '<p class="muted chart-caption">Products where demand is slowing or profit is thin. Worth reviewing.</p>'
            "</article>"
        )
        if stock_advice.get("watch_list"):
            advice_list(
                [
                    f'{row["product"]}: {row["suggested_action"]}'
                    for row in stock_advice["watch_list"]
                ]
            )
        else:
            render_html('<p class="muted">No products on the watch list.</p>')

render_footer()
