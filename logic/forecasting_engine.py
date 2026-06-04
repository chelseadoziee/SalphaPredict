"""Forecast future product sales from cleaned SalphaPredict datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from logic.forecast_evaluation import format_method_comparison_for_ui
from logic.forecast_methods import (
    COMPARABLE_BACKEND_METHODS,
    DEFAULT_FORECAST_METHOD,
    ForecastError,
    METHOD_DISPLAY_NAMES,
    MIN_HISTORY_MONTHS,
    METHOD_SMART_FORECAST,
    forecast_method_label,
    normalize_forecast_method,
    run_forecast,
)
from logic.mock_costs import apply_profit_columns
from logic.sales_analyser import SalesAnalysisError, _round_number, _validate_sales_dataframe

MAX_FORECAST_MONTHS = 6
DEFAULT_FORECAST_PERIOD = 1
TOP_PRODUCT_CHART_LIMIT = 10
TOP_SELLER_RANK = 3
TREND_STABLE_BAND = 0.05
ALLOWED_FORECAST_PERIODS = (1, 3, 6)
ALL_PRODUCTS_LABEL = "All products"


def _period_label(period: pd.Period) -> str:
    return str(period)


def _future_periods(last_period: pd.Period, count: int) -> list[str]:
    return [_period_label(last_period + offset) for offset in range(1, count + 1)]


def _normalize_forecast_model(model: str | None) -> str:
    """Backward-compatible alias for method normalization."""
    return normalize_forecast_method(model)


def _forecast_model_label(method: str) -> str:
    """User-facing forecast method label."""
    return forecast_method_label(method)


def _forecast_model_insight_prefix(method: str, _history_months: int) -> str:
    display = forecast_method_label(method)
    return f"Using {display},"


def _standard_to_overall_rows(
    standard: dict,
    forecast_periods: int,
    has_money: bool,
    has_profit: bool,
) -> list[dict]:
    rows: list[dict] = []
    for entry in standard["forecast"][:forecast_periods]:
        row: dict = {
            "period": entry["month"],
            "predicted_units": entry["forecast_units"],
        }
        if has_money:
            row["predicted_money"] = entry.get("expected_revenue")
        if has_profit:
            row["predicted_profit"] = entry.get("expected_profit")
        rows.append(row)
    return rows


def _confidence_detail_from_standard(standard: dict, history_months: int) -> dict:
    legacy = _forecast_confidence(history_months)
    return {
        "label": legacy["label"],
        "detail": legacy["detail"],
        "level": standard["confidence"],
        "explanation": standard["explanation"],
    }


def _trend_label(previous: float, latest: float) -> str:
    if previous == 0:
        return "up" if latest > 0 else "stable"

    change_pct = (latest - previous) / previous
    if change_pct > TREND_STABLE_BAND:
        return "up"
    if change_pct < -TREND_STABLE_BAND:
        return "down"
    return "stable"


def _trend_text(label: str) -> str:
    return {
        "up": "Sales going up",
        "down": "Sales going down",
        "stable": "Sales staying about the same",
    }[label]


def _normalize_forecast_periods(periods: int) -> int:
    if periods not in ALLOWED_FORECAST_PERIODS:
        return DEFAULT_FORECAST_PERIOD
    return periods


def _available_products(working: pd.DataFrame) -> list[str]:
    return (
        working.groupby("product")["quantity"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )


def _normalize_product_filter(product: str | None) -> str | None:
    if product is None:
        return None
    cleaned = str(product).strip()
    if not cleaned or cleaned.lower() in {"all", "all products", "__all__"}:
        return None
    return cleaned


def _resolve_product_filter(working: pd.DataFrame, product: str | None) -> str | None:
    selected = _normalize_product_filter(product)
    if selected is None:
        return None
    if selected in set(_available_products(working)):
        return selected
    return None


def _forecast_confidence(history_months: int) -> dict:
    if history_months >= 12:
        return {
            "label": "Good",
            "detail": "Based on 12 or more months of sales history.",
        }
    if history_months >= 8:
        return {
            "label": "Fair",
            "detail": "Based on several months of sales history.",
        }
    return {
        "label": "Basic",
        "detail": "Limited history so use this as a rough guide only.",
    }


def prepare_monthly_totals(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    working["period"] = working["sale_date"].dt.to_period("M")

    aggregates = {"quantity": ("quantity", "sum")}
    if "total_amount" in working.columns:
        aggregates["money_made"] = ("total_amount", "sum")
    if "profit" in working.columns:
        aggregates["profit"] = ("profit", "sum")

    monthly = (
        working.groupby("period", as_index=False)
        .agg(**aggregates)
        .sort_values("period")
    )
    return monthly


def prepare_monthly_product_series(df: pd.DataFrame, product: str) -> pd.DataFrame:
    working = df.copy()
    working["period"] = working["sale_date"].dt.to_period("M")
    product_rows = working[working["product"] == product]

    aggregates = {"quantity": ("quantity", "sum")}
    if "total_amount" in product_rows.columns:
        aggregates["money_made"] = ("total_amount", "sum")
    if "profit" in product_rows.columns:
        aggregates["profit"] = ("profit", "sum")

    monthly = (
        product_rows.groupby("period", as_index=False)
        .agg(**aggregates)
        .sort_values("period")
    )
    return monthly


def _format_naira(amount: float | None) -> str:
    if amount is None:
        return "—"
    return f"₦{float(amount):,.2f}"


def _join_product_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _suggested_action(trend: str, is_top_seller: bool, is_loss_making: bool) -> str:
    if is_loss_making:
        return "Review stock"
    if is_top_seller and trend == "up":
        return "Restock regularly"
    if is_top_seller:
        return "Keep stable"
    if trend == "up":
        return "Track closely"
    if trend == "down":
        return "Watch demand"
    return "Keep stable"


def _period_label_text(periods: int) -> str:
    if periods == 1:
        return "Next 1 month"
    return f"Next {periods} months"


def _sum_predictions(predictions: list[float], periods: int, round_as_int: bool) -> float | int:
    total = sum(predictions[:periods])
    if round_as_int:
        return int(round(total))
    return _round_number(total) or 0


def _build_forecast_rows(
    monthly: pd.DataFrame,
    value_column: str,
    periods: int,
    round_as_int: bool,
    method: str = DEFAULT_FORECAST_METHOD,
    selected_product: str | None = None,
) -> tuple[list[dict], list[str], list[float], list[str], list[float]]:
    """Adapter: run shared forecaster and return legacy row/series tuples."""
    standard = run_forecast(monthly, selected_product, periods, method)
    labels = standard["history_labels"]
    forecast_labels = standard["forecast_labels"]

    if round_as_int or value_column == "quantity":
        values = [float(value) for value in standard["history_units"]]
        forecast_values = [float(value) for value in standard["forecast_units"]]
        forecast_rows = [
            {"period": entry["month"], "predicted_units": entry["forecast_units"]}
            for entry in standard["forecast"]
        ]
    elif value_column == "money_made":
        values = [float(value) for value in (standard["history_money"] or [])]
        forecast_values = [float(value or 0) for value in (standard["forecast_money"] or [])]
        forecast_rows = [
            {"period": entry["month"], "predicted_money": entry.get("expected_revenue")}
            for entry in standard["forecast"]
        ]
    else:
        values = [float(value) for value in (standard["history_profit"] or [])]
        forecast_values = [float(value or 0) for value in (standard["forecast_profit"] or [])]
        forecast_rows = [
            {"period": entry["month"], "predicted_money": entry.get("expected_profit")}
            for entry in standard["forecast"]
        ]

    return forecast_rows, labels, values, forecast_labels, forecast_values


def _build_product_forecast_rows(
    working: pd.DataFrame,
    forecast_periods: int,
    loss_products: set[str],
    method: str = DEFAULT_FORECAST_METHOD,
) -> list[dict]:
    products = (
        working.groupby("product")["quantity"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )

    rows: list[dict] = []
    for rank, product in enumerate(products, start=1):
        product_monthly = prepare_monthly_product_series(working, product)
        if len(product_monthly) < MIN_HISTORY_MONTHS:
            continue

        try:
            standard = run_forecast(product_monthly, product, forecast_periods, method)
        except ForecastError:
            continue

        qty_values = [float(value) for value in product_monthly["quantity"].tolist()]
        forecast_entries = standard["forecast"]
        last_month_sold = int(qty_values[-1])
        next_month = int(forecast_entries[0]["forecast_units"])
        expected_sold = sum(entry["forecast_units"] for entry in forecast_entries)
        trend = _trend_label(last_month_sold, next_month)
        is_top_seller = rank <= TOP_SELLER_RANK
        is_loss_making = product in loss_products

        row = {
            "product": product,
            "last_month_sold": last_month_sold,
            "next_month_forecast": next_month,
            "expected_sold": expected_sold,
            "expected_money_made": None,
            "expected_profit": None,
            "trend": trend,
            "trend_label": _trend_text(trend),
            "suggested_action": _suggested_action(trend, is_top_seller, is_loss_making),
        }

        revenues = [entry.get("expected_revenue") for entry in forecast_entries]
        if any(value is not None for value in revenues):
            row["expected_money_made"] = _round_number(sum(value or 0 for value in revenues))

        profits = [entry.get("expected_profit") for entry in forecast_entries]
        if any(value is not None for value in profits):
            row["expected_profit"] = _round_number(sum(value or 0 for value in profits))

        rows.append(row)

    return rows


def generate_forecast_insight(
    overall_forecast: list[dict],
    product_forecasts: list[dict],
    has_money: bool,
    forecast_periods: int = DEFAULT_FORECAST_PERIOD,
    focused_product: str | None = None,
    forecast_method: str = DEFAULT_FORECAST_METHOD,
    history_months: int = MIN_HISTORY_MONTHS,
    forecast_explanation: str | None = None,
    chosen_method_display_name: str | None = None,
) -> list[str]:
    if not overall_forecast:
        return ["Not enough data to generate a forecast insight yet."]

    period_text = _period_label_text(forecast_periods).lower()
    expected_units = sum(row["predicted_units"] for row in overall_forecast[:forecast_periods])
    if forecast_method == METHOD_SMART_FORECAST and chosen_method_display_name:
        method_name = f"Smart Forecast ({chosen_method_display_name})"
    else:
        method_name = forecast_method_label(forecast_method)
    first = (
        f"Using {method_name}, SalphaPredict expects about {expected_units} "
        f"products sold over the {period_text}."
    )
    if forecast_explanation:
        first += f" {forecast_explanation}"
    if has_money:
        expected_money = sum(
            row.get("predicted_money") or 0 for row in overall_forecast[:forecast_periods]
        )
        if expected_money:
            first += f" That may bring in about {_format_naira(expected_money)}."

    paragraphs = [first]

    if focused_product and product_forecasts:
        row = product_forecasts[0]
        trend_phrase = {
            "up": "rise slightly",
            "down": "ease slightly",
            "stable": "stay fairly steady",
        }.get(row["trend"], "stay fairly steady")

        opening = (
            f"{focused_product} has shown {row['trend_label'].lower()} over the past sales period. "
            f"Based on the selected forecast period, demand is expected to {trend_phrase}."
        )
        paragraphs = [opening]

        if row["suggested_action"] in ("Restock regularly", "Track closely"):
            paragraphs.append(
                "This product may need closer stock tracking before the next restock cycle."
            )
        elif row["suggested_action"] in ("Watch demand", "Review stock"):
            paragraphs.append(
                "Review stock levels carefully before placing your next order for this product."
            )
        else:
            paragraphs.append(
                "Stock levels look fairly stable for now. Recheck after the next sales upload."
            )

        detail = f"About {row['expected_sold']} units may sell over the {period_text}"
        if row.get("expected_money_made") is not None:
            detail += f", with about {_format_naira(row['expected_money_made'])} in money made"
        if row.get("expected_profit") is not None:
            detail += f" and about {_format_naira(row['expected_profit'])} in profit"
        detail += "."
        paragraphs.append(detail)
        return paragraphs

    if product_forecasts:
        leader = product_forecasts[0]
        money_leader = max(
            product_forecasts,
            key=lambda row: row.get("expected_money_made") or 0,
        )
        second = product_forecasts[1] if len(product_forecasts) > 1 else None
        product_text = (
            f"{leader['product']} is expected to sell the most, "
            f"with about {leader['expected_sold']} products over the {period_text}"
        )
        if second:
            product_text += (
                f", followed by {second['product']} at about {second['expected_sold']} products"
            )
        product_text += "."
        paragraphs.append(product_text)

        if money_leader.get("expected_money_made") is not None:
            paragraphs.append(
                f"{money_leader['product']} may make the most money, "
                f"at about {_format_naira(money_leader['expected_money_made'])} "
                f"over the {period_text}."
            )

    restock = [
        row["product"]
        for row in product_forecasts
        if row["suggested_action"] in ("Restock regularly", "Track closely")
    ]
    watch = [
        row["product"]
        for row in product_forecasts
        if row["suggested_action"] in ("Watch demand", "Review stock")
    ]

    if restock:
        paragraphs.append(
            f"Products that may need restocking or closer tracking include "
            f"{_join_product_names(restock[:3])}."
        )
    elif watch:
        paragraphs.append(
            f"Before ordering more stock, keep an eye on "
            f"{_join_product_names(watch[:3])}."
        )
    else:
        paragraphs.append(
            "Overall sales look fairly steady in the forecast period. "
            "Use this page alongside the sales dashboard when planning stock."
        )

    return paragraphs


def _restock_status_label(suggested_action: str) -> str:
    return {
        "Restock regularly": "Restock soon",
        "Track closely": "Track closely",
        "Keep stable": "Stable",
        "Watch demand": "Watch before restocking",
        "Review stock": "Review stock",
    }.get(suggested_action, suggested_action)


def _restock_recommendation_text(
    product_name: str,
    product_row: dict,
    forecast_periods: int,
) -> str:
    action = product_row["suggested_action"]
    period_text = _period_label_text(forecast_periods).lower()
    expected_sold = product_row["expected_sold"]

    if action == "Restock regularly":
        return (
            f"Plan to restock {product_name} during the {period_text}. "
            f"About {expected_sold} units may sell, so keep stock levels ready before demand picks up."
        )
    if action == "Track closely":
        return (
            f"Track {product_name} closely during the {period_text}. "
            f"Demand may be rising, with about {expected_sold} units expected."
        )
    if action == "Watch demand":
        return (
            f"Be careful restocking {product_name} for the {period_text}. "
            f"Demand may soften, with about {expected_sold} units expected."
        )
    if action == "Review stock":
        return (
            f"Review stock for {product_name} before the {period_text}. "
            f"Profit or demand signals suggest a cautious restock approach."
        )
    return (
        f"{product_name} looks fairly stable for the {period_text}. "
        f"About {expected_sold} units are expected; adjust stock only if your warehouse levels are low."
    )


def _build_product_journey_chart(
    product_name: str,
    monthly: pd.DataFrame,
    forecast_periods: int,
    product_row: dict,
    has_money: bool,
    has_profit: bool,
    method: str = DEFAULT_FORECAST_METHOD,
    standard: dict | None = None,
) -> dict:
    """Build interactive journey-line data for a single-product forecast view."""
    build_periods = max(forecast_periods, MAX_FORECAST_MONTHS)
    if standard is None:
        standard = run_forecast(monthly, product_name, build_periods, method)

    hist_labels = standard["history_labels"]
    hist_units = standard["history_units"]
    fc_labels = standard["forecast_labels"]
    fc_units = standard["forecast_units"]
    hist_money = standard.get("history_money")
    fc_money = standard.get("forecast_money")
    hist_profit = standard.get("history_profit")
    fc_profit = standard.get("forecast_profit")

    trend_status = product_row["trend_label"]
    restock_advice = product_row["suggested_action"]
    restock_risk = restock_advice in ("Restock regularly", "Track closely")

    displayed_fc_labels = fc_labels[:forecast_periods]
    displayed_fc_units = [int(value) for value in fc_units[:forecast_periods]]

    history_count = len(hist_labels)
    peak_idx = (
        max(range(history_count), key=lambda index: hist_units[index]) if history_count else 0
    )
    low_idx = (
        min(range(history_count), key=lambda index: hist_units[index]) if history_count else 0
    )

    points: list[dict] = []
    for index, label in enumerate(hist_labels):
        is_now = index == history_count - 1
        phase = "now" if is_now else "history"
        marker_labels: list[str] = []
        marker_type = None

        if is_now:
            marker_labels.append("Now")
            marker_type = "now"
        if history_count > 1 and index == peak_idx:
            marker_labels.append("Peak month")
            marker_type = marker_type or "peak"
        if history_count > 1 and index == low_idx and low_idx != peak_idx:
            marker_labels.append("Lowest month")
            marker_type = marker_type or "lowest"

        points.append(
            {
                "month": label,
                "phase": phase,
                "units": int(hist_units[index]),
                "money": _round_number(hist_money[index]) if hist_money else None,
                "profit": _round_number(hist_profit[index]) if hist_profit else None,
                "is_forecast": False,
                "marker": marker_type,
                "marker_label": ", ".join(marker_labels) if marker_labels else None,
                "trend_status": trend_status,
                "restock_advice": restock_advice,
            }
        )

    for index, label in enumerate(displayed_fc_labels):
        marker_labels = []
        marker_type = None
        if index == 0:
            marker_labels.append("Forecast start")
            marker_type = "forecast_start"
        if restock_risk and index == 0:
            marker_labels.append("Restock point")
            marker_type = "restock" if marker_type is None else "forecast_start_restock"

        points.append(
            {
                "month": label,
                "phase": "forecast",
                "units": displayed_fc_units[index],
                "money": _round_number(fc_money[index]) if fc_money else None,
                "profit": _round_number(fc_profit[index]) if fc_profit else None,
                "is_forecast": True,
                "marker": marker_type,
                "marker_label": ", ".join(marker_labels) if marker_labels else None,
                "trend_status": trend_status,
                "restock_advice": restock_advice,
            }
        )

    marker_points = [
        {
            "month": point["month"],
            "units": point["units"],
            "type": point["marker"],
            "label": point["marker_label"],
        }
        for point in points
        if point.get("marker")
    ]

    return {
        "product": product_name,
        "points": points,
        "now_month": hist_labels[-1] if hist_labels else None,
        "forecast_start_month": displayed_fc_labels[0] if displayed_fc_labels else None,
        "history_count": history_count,
        "trend_status": trend_status,
        "restock_advice": restock_advice,
        "restock_risk": restock_risk,
        "markers": marker_points,
        "forecast_method": standard.get("ui_method", method),
        "forecast_model": standard.get("ui_method", method),
        "forecast_model_label": standard.get("display_name", forecast_method_label(method)),
    }


def _build_stock_groups(product_forecasts: list[dict]) -> dict:
    return {
        "restock_soon": [
            row for row in product_forecasts if row["suggested_action"] == "Restock regularly"
        ],
        "track_closely": [
            row for row in product_forecasts if row["suggested_action"] == "Track closely"
        ],
        "watch_list": [
            row
            for row in product_forecasts
            if row["suggested_action"] in ("Watch demand", "Review stock")
        ],
    }


def _build_charts(
    history_labels: list[str],
    history_units: list[float],
    forecast_labels: list[str],
    forecast_units: list[float],
    history_money: list[float] | None,
    forecast_money: list[float] | None,
    history_profit: list[float] | None,
    forecast_profit: list[float] | None,
    product_forecasts: list[dict],
    forecast_periods: int,
) -> dict:
    charts = {
        "products_sold": {
            "history_labels": history_labels,
            "history_values": [int(value) for value in history_units],
            "forecast_labels": forecast_labels[:forecast_periods],
            "forecast_values": [int(value) for value in forecast_units[:forecast_periods]],
        },
        "product_units": {
            "labels": [row["product"] for row in product_forecasts[:TOP_PRODUCT_CHART_LIMIT]],
            "values": [row["expected_sold"] for row in product_forecasts[:TOP_PRODUCT_CHART_LIMIT]],
        },
    }

    if history_money is not None and forecast_money is not None:
        charts["money_made"] = {
            "history_labels": history_labels,
            "history_values": history_money,
            "forecast_labels": forecast_labels[:forecast_periods],
            "forecast_values": forecast_money[:forecast_periods],
        }
        charts["product_money"] = {
            "labels": [
                row["product"]
                for row in product_forecasts[:TOP_PRODUCT_CHART_LIMIT]
                if row.get("expected_money_made") is not None
            ],
            "values": [
                row["expected_money_made"]
                for row in product_forecasts[:TOP_PRODUCT_CHART_LIMIT]
                if row.get("expected_money_made") is not None
            ],
        }

    if history_profit is not None and forecast_profit is not None:
        charts["profit"] = {
            "history_labels": history_labels,
            "history_values": history_profit,
            "forecast_labels": forecast_labels[:forecast_periods],
            "forecast_values": forecast_profit[:forecast_periods],
        }
        profit_rows = [
            row
            for row in product_forecasts[:TOP_PRODUCT_CHART_LIMIT]
            if row.get("expected_profit") is not None
        ]
        charts["product_profit"] = {
            "labels": [row["product"] for row in profit_rows],
            "values": [row["expected_profit"] for row in profit_rows],
        }

    return charts


def forecast_sales_dataframe(
    df: pd.DataFrame,
    forecast_periods: int = DEFAULT_FORECAST_PERIOD,
    product: str | None = None,
    model: str | None = None,
    method: str | None = None,
) -> dict:
    """Forecast overall and product-level sales from cleaned data."""
    forecast_periods = _normalize_forecast_periods(forecast_periods)
    forecast_method = normalize_forecast_method(method or model)
    working = _validate_sales_dataframe(df)
    working, _ = apply_profit_columns(working)

    product_names = _available_products(working)
    selected_product = _resolve_product_filter(working, product)
    forecast_working = working
    if selected_product:
        forecast_working = working[working["product"] == selected_product].copy()

    monthly = prepare_monthly_totals(forecast_working)
    if len(monthly) < MIN_HISTORY_MONTHS:
        raise ForecastError(
            f"Need at least {MIN_HISTORY_MONTHS} months of sales history to forecast. "
            f"This file only has {len(monthly)} month(s)."
        )

    build_periods = max(forecast_periods, MAX_FORECAST_MONTHS)
    standard_forecast = run_forecast(monthly, selected_product, build_periods, forecast_method)

    has_money = "money_made" in monthly.columns
    has_profit = "profit" in monthly.columns
    overall_rows = _standard_to_overall_rows(
        standard_forecast, build_periods, has_money, has_profit
    )
    history_labels = standard_forecast["history_labels"]
    history_units = [float(value) for value in standard_forecast["history_units"]]
    forecast_labels = standard_forecast["forecast_labels"]
    forecast_units = [float(value) for value in standard_forecast["forecast_units"]]
    history_money = (
        [float(value) for value in standard_forecast["history_money"]]
        if standard_forecast.get("history_money")
        else None
    )
    forecast_money = (
        [float(value or 0) for value in standard_forecast["forecast_money"]]
        if standard_forecast.get("forecast_money")
        else None
    )
    history_profit = (
        [float(value) for value in standard_forecast["history_profit"]]
        if standard_forecast.get("history_profit")
        else None
    )
    forecast_profit = (
        [float(value or 0) for value in standard_forecast["forecast_profit"]]
        if standard_forecast.get("forecast_profit")
        else None
    )

    loss_products: set[str] = set()
    if has_profit:
        product_profit = working.groupby("product")["profit"].sum()
        loss_products = set(product_profit[product_profit < 0].index.tolist())

    product_forecasts_all = _build_product_forecast_rows(
        working,
        forecast_periods,
        loss_products,
        method=forecast_method,
    )
    if selected_product:
        product_forecasts = [
            row for row in product_forecasts_all if row["product"] == selected_product
        ]
        if not product_forecasts:
            product_months = len(prepare_monthly_product_series(working, selected_product))
            raise ForecastError(
                f'Need at least {MIN_HISTORY_MONTHS} months of history for "{selected_product}". '
                f"This product only has {product_months} month(s) with sales."
            )
    else:
        product_forecasts = product_forecasts_all

    stock_groups = _build_stock_groups(product_forecasts)
    confidence = _confidence_detail_from_standard(standard_forecast, len(monthly))

    displayed_overall = overall_rows[:forecast_periods]
    expected_products_sold = sum(row["predicted_units"] for row in displayed_overall)
    expected_money_made = (
        _round_number(sum(row.get("predicted_money") or 0 for row in displayed_overall))
        if has_money
        else None
    )
    expected_profit = (
        _round_number(sum(row.get("predicted_profit") or 0 for row in displayed_overall))
        if has_profit
        else None
    )

    restock_alerts = len(stock_groups["restock_soon"]) + len(stock_groups["track_closely"])
    if selected_product:
        top_product = selected_product
    else:
        top_product = product_forecasts[0]["product"] if product_forecasts else "N/A"

    last_history_units = int(history_units[-1])
    first_forecast_units = int(forecast_units[0])
    overall_trend = _trend_label(last_history_units, first_forecast_units)

    view_mode = "comparison"
    product_focus: dict | None = None

    if selected_product:
        view_mode = "product_journey"
        product_row = product_forecasts[0]
        charts = {
            "journey_line": _build_product_journey_chart(
                selected_product,
                monthly,
                forecast_periods,
                product_row,
                has_money,
                has_profit,
                method=forecast_method,
                standard=standard_forecast,
            ),
        }
        product_focus = {
            "product": selected_product,
            "expected_products_sold": expected_products_sold,
            "expected_money_made": expected_money_made,
            "expected_profit": expected_profit,
            "has_profit": has_profit,
            "has_money": has_money,
            "forecast_confidence": confidence["label"],
            "forecast_confidence_detail": confidence["detail"],
            "restock_status": _restock_status_label(product_row["suggested_action"]),
            "trend_direction": _trend_text(overall_trend),
            "trend": overall_trend,
            "last_month_sold": product_row["last_month_sold"],
            "next_month_forecast": product_row["next_month_forecast"],
            "suggested_action": product_row["suggested_action"],
            "restock_recommendation": _restock_recommendation_text(
                selected_product,
                product_row,
                forecast_periods,
            ),
        }
    else:
        charts = _build_charts(
            history_labels,
            history_units,
            forecast_labels,
            forecast_units,
            history_money,
            forecast_money,
            history_profit,
            forecast_profit,
            product_forecasts,
            forecast_periods,
        )

    what_this_means = generate_forecast_insight(
        overall_rows,
        product_forecasts,
        has_money,
        forecast_periods,
        focused_product=selected_product,
        forecast_method=forecast_method,
        history_months=len(monthly),
        forecast_explanation=standard_forecast.get("explanation"),
        chosen_method_display_name=standard_forecast.get("chosen_method_display_name"),
    )

    method_comparison = format_method_comparison_for_ui(
        standard_forecast.get("method_comparison")
    )

    product_options = [{"value": "", "label": ALL_PRODUCTS_LABEL}]
    product_options.extend({"value": name, "label": name} for name in product_names)

    return {
        "history_months": len(monthly),
        "forecast_periods": forecast_periods,
        "forecast_period_label": _period_label_text(forecast_periods),
        "forecast_months": forecast_periods,
        "selected_product": selected_product,
        "view_mode": view_mode,
        "product_focus": product_focus,
        "forecast_method": forecast_method,
        "forecast_model": forecast_method,
        "forecast_model_label": standard_forecast["display_name"],
        "chosen_method_display_name": standard_forecast.get("chosen_method_display_name"),
        "resolved_method_key": standard_forecast.get("resolved_method_key"),
        "method_comparison": method_comparison,
        "forecast_explanation": standard_forecast.get("explanation"),
        "is_smart_forecast": forecast_method == METHOD_SMART_FORECAST,
        "smart_forecast_methods_tested": [
            {"key": key, "label": METHOD_DISPLAY_NAMES[key]}
            for key in COMPARABLE_BACKEND_METHODS
        ],
        "standard_forecast": standard_forecast,
        "history_range": {
            "start": _period_label(monthly["period"].iloc[0]),
            "end": _period_label(monthly["period"].iloc[-1]),
        },
        "controls": {
            "forecast_period_options": [
                {"value": 1, "label": "Next 1 month"},
                {"value": 3, "label": "Next 3 months"},
                {"value": 6, "label": "Next 6 months"},
            ],
            "product_options": product_options,
            "selected_product": selected_product or "",
            "product_filter": selected_product or ALL_PRODUCTS_LABEL,
        },
        "summary": {
            "expected_products_sold": expected_products_sold,
            "expected_money_made": expected_money_made,
            "expected_profit": expected_profit,
            "has_profit": has_profit,
            "restock_alerts": restock_alerts,
            "top_forecast_product": top_product,
            "forecast_confidence": confidence["label"],
            "forecast_confidence_detail": confidence["detail"],
        },
        "overall_trend": {
            "direction": overall_trend,
            "label": _trend_text(overall_trend),
        },
        "overall_forecast": displayed_overall,
        "product_forecasts": product_forecasts,
        "forecast_table": product_forecasts,
        "forecast_insight": what_this_means,
        "what_this_means": what_this_means,
        "stock_advice": stock_groups,
        "charts": charts,
    }


def list_forecast_products(filepath: Path) -> dict:
    """Return product names available for forecast filtering."""
    if not filepath.exists():
        return {
            "success": False,
            "error": f"Cleaned data file not found: {filepath.name}",
            "products": [],
        }

    try:
        df = pd.read_csv(filepath, parse_dates=["sale_date"])
        working = _validate_sales_dataframe(df)
        return {"success": True, "products": _available_products(working)}
    except (SalesAnalysisError, ForecastError) as exc:
        return {"success": False, "error": str(exc), "products": []}
    except Exception as exc:
        return {"success": False, "error": f"Could not read cleaned data: {exc}", "products": []}


def forecast_sales_file(
    filepath: Path,
    forecast_periods: int = DEFAULT_FORECAST_PERIOD,
    product: str | None = None,
    model: str | None = None,
    method: str | None = None,
) -> dict:
    """Load a cleaned CSV file and return a UI-friendly forecast report."""
    if not filepath.exists():
        return {
            "success": False,
            "error": f"Cleaned data file not found: {filepath.name}",
        }

    try:
        df = pd.read_csv(filepath, parse_dates=["sale_date"])
    except Exception as exc:
        return {
            "success": False,
            "error": f"Could not read cleaned data: {exc}",
        }

    try:
        from logic.forecast_tracking import forecast_logging_scope

        with forecast_logging_scope(filepath.name):
            report = forecast_sales_dataframe(
                df,
                forecast_periods=forecast_periods,
                product=product,
                model=model,
                method=method or model,
            )
    except (ForecastError, SalesAnalysisError) as exc:
        return {
            "success": False,
            "error": str(exc),
        }

    return {
        "success": True,
        "source_file": filepath.name,
        **report,
    }
