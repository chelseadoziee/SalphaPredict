from __future__ import annotations

import math
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from logic.formatters import format_naira_compact

SALPHA_YELLOW = "#ffdd00"
SALPHA_BLACK = "#000000"
SALPHA_WARM_GREY = "#393d46"
SALPHA_COOL_GREY = "#f0ece9"


def _build_money_axis(values: list[float | None], title: str = "Money made") -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    max_value = max(clean) if clean else 0

    if max_value <= 0:
        return {"title": title, "tickvals": [0], "ticktext": ["₦0"], "automargin": True}

    tick_count = 5
    raw_step = max_value / (tick_count - 1)
    magnitude = 10 ** math.floor(math.log10(raw_step)) if raw_step > 0 else 1
    step = max(magnitude, math.ceil(raw_step / magnitude) * magnitude)
    tickvals: list[float] = []
    ticktext: list[str] = []

    value = 0.0
    while value <= max_value + step * 0.01 and len(tickvals) < tick_count:
        tickvals.append(value)
        ticktext.append(format_naira_compact(value))
        value += step

    return {"title": title, "tickvals": tickvals, "ticktext": ticktext, "automargin": True}


def _base_layout(**extra: Any) -> dict[str, Any]:
    layout = {
        "height": 280,
        "margin": {"t": 12, "r": 12, "b": 48, "l": 52},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Arial, sans-serif", "color": "#000000", "size": 12},
    }
    layout.update(extra)
    return layout


def show_figure(fig: go.Figure) -> None:
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_dashboard_chart(charts: dict[str, Any], chart_key: str) -> None:
    """Render one sales dashboard chart directly beneath its card title."""
    if chart_key == "monthly_quantity" and charts.get("monthly_trend"):
        monthly = charts["monthly_trend"]
        fig = go.Figure(
            go.Bar(
                x=monthly["labels"],
                y=monthly["quantity"],
                marker_color=SALPHA_YELLOW,
                hovertemplate="Month: %{x}<br>Products sold: %{y}<extra></extra>",
            )
        )
        fig.update_layout(
            **_base_layout(
                xaxis={"title": "Month", "automargin": True},
                yaxis={"title": "Products sold", "automargin": True, "rangemode": "tozero"},
                showlegend=False,
            )
        )
        show_figure(fig)
        return

    if chart_key == "monthly_revenue" and charts.get("monthly_trend"):
        monthly = charts["monthly_trend"]
        if monthly.get("revenue") and any(value is not None for value in monthly["revenue"]):
            fig = go.Figure(
                go.Bar(
                    x=monthly["labels"],
                    y=monthly["revenue"],
                    marker_color=SALPHA_BLACK,
                    customdata=[format_naira_compact(value) for value in monthly["revenue"]],
                    hovertemplate="Month: %{x}<br>Money made: %{customdata}<extra></extra>",
                )
            )
            yaxis = _build_money_axis(monthly["revenue"])
            yaxis["rangemode"] = "tozero"
            fig.update_layout(
                **_base_layout(
                    xaxis={"title": "Month", "automargin": True},
                    yaxis=yaxis,
                    showlegend=False,
                )
            )
            show_figure(fig)
        return

    if chart_key == "top_products" and charts.get("top_products"):
        series = charts["top_products"]
        fig = go.Figure(
            go.Bar(
                x=series["quantity"],
                y=series["labels"],
                orientation="h",
                marker_color=SALPHA_BLACK,
                hovertemplate="Product: %{y}<br>Products sold: %{x}<extra></extra>",
            )
        )
        fig.update_layout(
            **_base_layout(
                margin={"t": 12, "r": 12, "b": 48, "l": 120},
                xaxis={"title": "Products sold", "automargin": True, "rangemode": "tozero"},
                yaxis={"title": "Product", "automargin": True, "categoryorder": "total ascending"},
                showlegend=False,
            )
        )
        show_figure(fig)
        return

    if chart_key == "revenue_by_product" and charts.get("revenue_by_product"):
        series = charts["revenue_by_product"]
        fig = go.Figure(
            go.Bar(
                x=series["revenue"],
                y=series["labels"],
                orientation="h",
                marker_color=SALPHA_YELLOW,
                customdata=[format_naira_compact(value) for value in series["revenue"]],
                hovertemplate="Product: %{y}<br>Money made: %{customdata}<extra></extra>",
            )
        )
        xaxis = _build_money_axis(series["revenue"])
        xaxis["rangemode"] = "tozero"
        fig.update_layout(
            **_base_layout(
                margin={"t": 12, "r": 12, "b": 48, "l": 132},
                xaxis=xaxis,
                yaxis={"title": "Product", "automargin": True, "categoryorder": "total ascending"},
                showlegend=False,
            )
        )
        show_figure(fig)


def dashboard_charts(charts: dict[str, Any]) -> None:
    for chart_key in (
        "monthly_quantity",
        "monthly_revenue",
        "top_products",
        "revenue_by_product",
    ):
        render_dashboard_chart(charts, chart_key)


def _history_forecast_figure(series: dict[str, Any], y_title: str, is_money: bool) -> go.Figure:
    all_labels = series["history_labels"] + series["forecast_labels"]
    history_y = series["history_values"] + [None] * len(series["forecast_labels"])
    forecast_y = [None] * len(series["history_labels"]) + series["forecast_values"]

    if is_money:
        yaxis = _build_money_axis(series["history_values"] + series["forecast_values"], y_title)
    else:
        yaxis = {"title": y_title, "automargin": True, "rangemode": "tozero"}

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=all_labels,
            y=history_y,
            name="Past",
            marker_color=SALPHA_BLACK,
            hovertemplate=f"Month: %{{x}}<br>{y_title}: %{{y}}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=all_labels,
            y=forecast_y,
            name="Expected",
            marker_color=SALPHA_YELLOW,
            hovertemplate=f"Month: %{{x}}<br>{y_title}: %{{y}}<extra></extra>",
        )
    )
    fig.update_layout(
        **_base_layout(
            xaxis={"title": "Month", "automargin": True},
            yaxis=yaxis,
            barmode="overlay",
            legend={"orientation": "h", "y": 1.02, "x": 0.5, "xanchor": "center"},
        )
    )
    return fig


def _horizontal_product_figure(series: dict[str, Any], x_title: str, is_money: bool) -> go.Figure:
    customdata = None
    hovertemplate = "Product: %{y}<br>Units: %{x}<extra></extra>"
    if is_money:
        customdata = [format_naira_compact(value) for value in series["values"]]
        hovertemplate = "Product: %{y}<br>Value: %{customdata}<extra></extra>"

    fig = go.Figure(
        go.Bar(
            x=series["values"],
            y=series["labels"],
            orientation="h",
            marker_color=SALPHA_YELLOW,
            customdata=customdata,
            hovertemplate=hovertemplate,
        )
    )
    xaxis: dict[str, Any]
    if is_money:
        xaxis = _build_money_axis(series["values"], x_title)
        xaxis["rangemode"] = "tozero"
    else:
        xaxis = {"title": x_title, "automargin": True, "rangemode": "tozero"}

    fig.update_layout(
        **_base_layout(
            margin={"t": 12, "r": 12, "b": 48, "l": 132},
            xaxis=xaxis,
            yaxis={"title": "Product", "automargin": True, "categoryorder": "total ascending"},
            showlegend=False,
        )
    )
    return fig


def product_journey_chart(journey: dict[str, Any]) -> None:
    """Render the single-product forecast journey line chart."""
    points = journey.get("points", [])
    if not points:
        return

    product_name = journey.get("product", "Product")
    history_points = [point for point in points if not point.get("is_forecast")]
    forecast_points = [point for point in points if point.get("is_forecast")]
    if not history_points:
        return

    last_history = history_points[-1]
    history_x = [point["month"] for point in history_points]
    history_y = [point["units"] for point in history_points]
    forecast_x = [last_history["month"]] + [point["month"] for point in forecast_points]
    forecast_y = [last_history["units"]] + [point["units"] for point in forecast_points]

    def hover_text(point: dict[str, Any]) -> str:
        lines = [f"Month: {point['month']}", f"Product: {product_name}"]
        if point.get("is_forecast"):
            lines.append(f"Expected units sold: {point['units']}")
        else:
            lines.append(f"Actual units sold: {point['units']}")
        if point.get("money") is not None:
            label = "Expected revenue" if point.get("is_forecast") else "Revenue"
            lines.append(f"{label}: {format_naira_compact(point['money'])}")
        if point.get("profit") is not None:
            label = "Expected profit" if point.get("is_forecast") else "Profit"
            lines.append(f"{label}: {format_naira_compact(point['profit'])}")
        lines.append(f"Trend status: {point.get('trend_status', '')}")
        lines.append(f"Restock advice: {point.get('restock_advice', '')}")
        if point.get("marker_label"):
            lines.append(f"Marker: {point['marker_label']}")
        return "<br>".join(lines)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history_x,
            y=history_y,
            mode="lines+markers",
            name="Past sales",
            line={"color": SALPHA_BLACK, "width": 3, "shape": "spline"},
            marker={"color": SALPHA_BLACK, "size": 8, "line": {"color": "#ffffff", "width": 1.5}},
            hovertext=[hover_text(point) for point in history_points],
            hoverinfo="text",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast_x,
            y=forecast_y,
            mode="lines+markers",
            name="Forecast",
            line={"color": SALPHA_YELLOW, "width": 3, "dash": "dash", "shape": "spline"},
            marker={"color": SALPHA_YELLOW, "size": 9, "line": {"color": SALPHA_BLACK, "width": 1.5}},
            hovertext=[hover_text(point) for point in [last_history, *forecast_points]],
            hoverinfo="text",
        )
    )

    marker_points = [point for point in points if point.get("marker")]
    if marker_points:
        fig.add_trace(
            go.Scatter(
                x=[point["month"] for point in marker_points],
                y=[point["units"] for point in marker_points],
                mode="markers+text",
                name="Markers",
                text=[point.get("marker_label") or "" for point in marker_points],
                textposition="top center",
                textfont={"size": 11, "color": SALPHA_BLACK},
                hovertext=[hover_text(point) for point in marker_points],
                hoverinfo="text",
                marker={
                    "size": 14,
                    "color": SALPHA_YELLOW,
                    "line": {"color": "#ffffff", "width": 2},
                    "symbol": "diamond",
                },
                showlegend=False,
            )
        )

    shapes = []
    if journey.get("forecast_start_month"):
        shapes.append(
            {
                "type": "line",
                "x0": journey["forecast_start_month"],
                "x1": journey["forecast_start_month"],
                "y0": 0,
                "y1": 1,
                "yref": "paper",
                "line": {"color": "rgba(57, 61, 70, 0.35)", "width": 2, "dash": "dot"},
            }
        )

    y_max = max(point["units"] for point in points) or 1
    fig.update_layout(
        **_base_layout(
            height=420,
            margin={"t": 28, "r": 20, "b": 56, "l": 56},
            xaxis={"title": "Month", "automargin": True, "showgrid": True, "gridcolor": "rgba(0,0,0,0.06)"},
            yaxis={
                "title": "Units sold",
                "automargin": True,
                "rangemode": "tozero",
                "range": [0, y_max * 1.18],
                "showgrid": True,
                "gridcolor": "rgba(0,0,0,0.06)",
            },
            shapes=shapes,
            legend={"orientation": "h", "y": 1.08, "x": 0, "xanchor": "left"},
            hovermode="closest",
        )
    )
    show_figure(fig)


def render_forecast_chart(charts: dict[str, Any], chart_key: str) -> None:
    """Render one forecast chart directly beneath its card title."""
    if chart_key == "journey_line":
        if charts.get("journey_line"):
            product_journey_chart(charts["journey_line"])
        return

    if chart_key == "products_sold" and charts.get("products_sold"):
        show_figure(_history_forecast_figure(charts["products_sold"], "Products sold", False))
    elif chart_key == "money_made" and charts.get("money_made"):
        show_figure(_history_forecast_figure(charts["money_made"], "Money made", True))
    elif chart_key == "profit" and charts.get("profit"):
        show_figure(_history_forecast_figure(charts["profit"], "Profit", True))
    elif chart_key == "product_units" and charts.get("product_units"):
        show_figure(_horizontal_product_figure(charts["product_units"], "Expected sold", False))
    elif chart_key == "product_money" and charts.get("product_money"):
        show_figure(_horizontal_product_figure(charts["product_money"], "Expected money made", True))
    elif chart_key == "product_profit" and charts.get("product_profit"):
        show_figure(_horizontal_product_figure(charts["product_profit"], "Expected profit", True))


def forecast_charts(charts: dict[str, Any]) -> None:
    if charts.get("journey_line"):
        render_forecast_chart(charts, "journey_line")
        return

    for chart_key in (
        "products_sold",
        "money_made",
        "profit",
        "product_units",
        "product_money",
        "product_profit",
    ):
        render_forecast_chart(charts, chart_key)


def profit_loss_charts(charts: dict[str, Any]) -> None:
    if charts.get("monthly_profit_and_loss"):
        monthly = charts["monthly_profit_and_loss"]
        axis_values = monthly["gross_profit"] + monthly["loss"]
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=monthly["labels"],
                y=monthly["gross_profit"],
                name="Gross profit",
                marker_color=SALPHA_YELLOW,
                customdata=[format_naira_compact(value) for value in monthly["gross_profit"]],
                hovertemplate="Month: %{x}<br>Gross profit: %{customdata}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                x=monthly["labels"],
                y=monthly["loss"],
                name="Loss",
                marker_color=SALPHA_BLACK,
                customdata=[format_naira_compact(value) for value in monthly["loss"]],
                hovertemplate="Month: %{x}<br>Loss: %{customdata}<extra></extra>",
            )
        )
        yaxis = _build_money_axis(axis_values, "Amount")
        yaxis["rangemode"] = "tozero"
        fig.update_layout(
            **_base_layout(
                xaxis={"title": "Month", "automargin": True},
                yaxis=yaxis,
                barmode="group",
                legend={"orientation": "h", "y": 1.02, "x": 0.5, "xanchor": "center"},
            )
        )
        show_figure(fig)

    if charts.get("monthly_money_and_cost"):
        monthly = charts["monthly_money_and_cost"]
        axis_values = monthly["money_made"] + monthly["total_cost"]
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=monthly["labels"],
                y=monthly["money_made"],
                name="Money made",
                marker_color=SALPHA_BLACK,
                customdata=[format_naira_compact(value) for value in monthly["money_made"]],
                hovertemplate="Month: %{x}<br>Money made: %{customdata}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                x=monthly["labels"],
                y=monthly["total_cost"],
                name="Total cost",
                marker_color=SALPHA_WARM_GREY,
                customdata=[format_naira_compact(value) for value in monthly["total_cost"]],
                hovertemplate="Month: %{x}<br>Total cost: %{customdata}<extra></extra>",
            )
        )
        yaxis = _build_money_axis(axis_values, "Amount")
        yaxis["rangemode"] = "tozero"
        fig.update_layout(
            **_base_layout(
                xaxis={"title": "Month", "automargin": True},
                yaxis=yaxis,
                barmode="group",
                legend={"orientation": "h", "y": 1.02, "x": 0.5, "xanchor": "center"},
            )
        )
        show_figure(fig)

    if charts.get("profit_by_product") and charts["profit_by_product"].get("labels"):
        products = charts["profit_by_product"]
        fig = go.Figure(
            go.Bar(
                x=products["profit"],
                y=products["labels"],
                orientation="h",
                marker_color=SALPHA_YELLOW,
                customdata=[format_naira_compact(value) for value in products["profit"]],
                hovertemplate="Product: %{y}<br>Gross profit: %{customdata}<extra></extra>",
            )
        )
        xaxis = _build_money_axis(products["profit"], "Gross profit")
        xaxis["rangemode"] = "tozero"
        fig.update_layout(
            **_base_layout(
                margin={"t": 12, "r": 12, "b": 48, "l": 132},
                xaxis=xaxis,
                yaxis={"title": "Product", "automargin": True, "categoryorder": "total ascending"},
                showlegend=False,
            )
        )
        show_figure(fig)

    if charts.get("loss_by_product"):
        products = charts["loss_by_product"]
        fig = go.Figure(
            go.Bar(
                x=products["loss"],
                y=products["labels"],
                orientation="h",
                marker_color=SALPHA_BLACK,
                customdata=[format_naira_compact(value) for value in products["loss"]],
                hovertemplate="Product: %{y}<br>Loss: %{customdata}<extra></extra>",
            )
        )
        xaxis = _build_money_axis(products["loss"], "Loss")
        xaxis["rangemode"] = "tozero"
        fig.update_layout(
            **_base_layout(
                margin={"t": 12, "r": 12, "b": 48, "l": 132},
                xaxis=xaxis,
                yaxis={"title": "Product", "automargin": True, "categoryorder": "total ascending"},
                showlegend=False,
            )
        )
        show_figure(fig)


def stock_advice_charts(charts: dict[str, Any]) -> None:
    if not charts.get("suggested_stock"):
        return

    stock = charts["suggested_stock"]
    fig = go.Figure(
        go.Bar(
            x=stock["values"],
            y=stock["labels"],
            orientation="h",
            marker_color=SALPHA_YELLOW,
            hovertemplate="Product: %{y}<br>Suggested stock: %{x}<extra></extra>",
        )
    )
    fig.update_layout(
        **_base_layout(
            margin={"t": 12, "r": 12, "b": 48, "l": 132},
            xaxis={"title": "Suggested units", "automargin": True, "rangemode": "tozero"},
            yaxis={"title": "Product", "automargin": True, "categoryorder": "total ascending"},
            showlegend=False,
        )
    )
    show_figure(fig)
