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


def dashboard_charts(charts: dict[str, Any]) -> None:
    if charts.get("monthly_trend"):
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

    if charts.get("top_products"):
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

    if charts.get("revenue_by_product"):
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


def forecast_charts(charts: dict[str, Any]) -> None:
    if charts.get("products_sold"):
        show_figure(_history_forecast_figure(charts["products_sold"], "Products sold", False))
    if charts.get("money_made"):
        show_figure(_history_forecast_figure(charts["money_made"], "Money made", True))
    if charts.get("profit"):
        show_figure(_history_forecast_figure(charts["profit"], "Profit", True))
    if charts.get("product_units"):
        show_figure(_horizontal_product_figure(charts["product_units"], "Expected sold", False))
    if charts.get("product_money"):
        show_figure(_horizontal_product_figure(charts["product_money"], "Expected money made", True))
    if charts.get("product_profit"):
        show_figure(_horizontal_product_figure(charts["product_profit"], "Expected profit", True))


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
