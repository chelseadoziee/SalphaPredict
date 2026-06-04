from __future__ import annotations

import streamlit as st

import config
from logic.forecasting_engine import ALL_PRODUCTS_LABEL, forecast_sales_file, list_forecast_products
from streamlit_ui.charts import forecast_charts
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
    f'See what may sell next. SalphaPredict picks the most accurate forecast method for your data. '
    f'Source: <strong>{forecast_report["source_file"]}</strong> '
    f'({forecast_report["history_range"]["start"]} to {forecast_report["history_range"]["end"]}).',
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
        f'Where <strong>{focus["product"]}</strong> has been, where it is now, and where it may go next.'
    )
    if chosen_label:
        journey_caption += (
            f' Smart Forecast is using <strong>{chosen_label}</strong>.'
        )
    chart_card("Forecast journey", journey_caption)
    forecast_charts(forecast_report.get("charts", {}))

    col1, col2 = st.columns(2)
    with col1:
        section_card(
            "Revenue outlook",
            f'Money made for {focus["product"]} over {forecast_report["forecast_period_label"].lower()}.',
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
            "Profit outlook",
            f'Expected profit for {focus["product"]} over {forecast_report["forecast_period_label"].lower()}.',
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

    insight_summary("What this could mean", forecast_report.get("what_this_means", []))
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
                    f'{row["product"]}: {row["suggested_action"]} (about {row["expected_sold"]} units)'
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
                    f'{row["product"]}: {row["suggested_action"]} (about {row["expected_sold"]} units)'
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
                    f'{row["product"]}: {row["suggested_action"]}'
                    for row in stock_advice["watch_list"]
                ]
            )
        else:
            render_html('<p class="muted">No products on the watch list.</p>')

render_footer()
