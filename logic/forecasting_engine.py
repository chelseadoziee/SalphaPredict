"""Forecast future product sales from cleaned SalphaPredict datasets."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from logic.mock_costs import apply_profit_columns
from logic.sales_analyser import SalesAnalysisError, _round_number, _validate_sales_dataframe

MIN_HISTORY_MONTHS = 4
MAX_FORECAST_MONTHS = 6
DEFAULT_FORECAST_PERIOD = 1
TOP_PRODUCT_CHART_LIMIT = 10
TOP_SELLER_RANK = 3
TREND_STABLE_BAND = 0.05
ALLOWED_FORECAST_PERIODS = (1, 3, 6)


class ForecastError(Exception):
    """Raised when cleaned sales data cannot be forecast."""


def _period_label(period: pd.Period) -> str:
    return str(period)


def _future_periods(last_period: pd.Period, count: int) -> list[str]:
    return [_period_label(last_period + offset) for offset in range(1, count + 1)]


def _fit_linear_forecast(values: list[float], periods: int) -> list[float]:
    if len(values) < MIN_HISTORY_MONTHS:
        raise ForecastError(
            f"Need at least {MIN_HISTORY_MONTHS} months of history to forecast."
        )

    x_values = np.arange(len(values)).reshape(-1, 1)
    y_values = np.array(values, dtype=float)
    model = LinearRegression()
    model.fit(x_values, y_values)

    future_x = np.arange(len(values), len(values) + periods).reshape(-1, 1)
    predictions = model.predict(future_x)
    return [float(max(0, value)) for value in predictions]


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
) -> tuple[list[dict], list[str], list[float], list[str], list[float]]:
    labels = [_period_label(period) for period in monthly["period"]]
    values = [float(value) for value in monthly[value_column].tolist()]
    predictions = _fit_linear_forecast(values, periods)
    forecast_labels = _future_periods(monthly["period"].iloc[-1], periods)

    forecast_rows = []
    for label, predicted in zip(forecast_labels, predictions):
        row = {"period": label}
        if round_as_int:
            row["predicted_units"] = int(round(predicted))
        else:
            row["predicted_money"] = _round_number(predicted)
        forecast_rows.append(row)

    if round_as_int:
        forecast_values = [row["predicted_units"] for row in forecast_rows]
    else:
        forecast_values = [row["predicted_money"] for row in forecast_rows]

    return forecast_rows, labels, values, forecast_labels, forecast_values


def _build_product_forecast_rows(
    working: pd.DataFrame,
    forecast_periods: int,
    loss_products: set[str],
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

        qty_values = [float(value) for value in product_monthly["quantity"].tolist()]
        try:
            qty_predictions = _fit_linear_forecast(qty_values, forecast_periods)
        except ForecastError:
            continue

        last_month_sold = int(qty_values[-1])
        next_month = int(round(qty_predictions[0]))
        expected_sold = _sum_predictions(qty_predictions, forecast_periods, round_as_int=True)
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

        if "money_made" in product_monthly.columns:
            money_values = [float(value) for value in product_monthly["money_made"].tolist()]
            try:
                money_predictions = _fit_linear_forecast(money_values, forecast_periods)
                row["expected_money_made"] = _sum_predictions(
                    money_predictions, forecast_periods, round_as_int=False
                )
            except ForecastError:
                pass

        if "profit" in product_monthly.columns:
            profit_values = [float(value) for value in product_monthly["profit"].tolist()]
            try:
                profit_predictions = _fit_linear_forecast(profit_values, forecast_periods)
                row["expected_profit"] = _sum_predictions(
                    profit_predictions, forecast_periods, round_as_int=False
                )
            except ForecastError:
                pass

        rows.append(row)

    return rows


def generate_forecast_insight(
    overall_forecast: list[dict],
    product_forecasts: list[dict],
    has_money: bool,
    forecast_periods: int = DEFAULT_FORECAST_PERIOD,
) -> list[str]:
    if not overall_forecast:
        return ["Not enough data to generate a forecast insight yet."]

    period_text = _period_label_text(forecast_periods).lower()
    expected_units = sum(row["predicted_units"] for row in overall_forecast[:forecast_periods])

    first = (
        f"Based on past monthly sales, SalphaPredict expects about {expected_units} "
        f"products sold over the {period_text}."
    )
    if has_money:
        expected_money = sum(
            row.get("predicted_money") or 0 for row in overall_forecast[:forecast_periods]
        )
        if expected_money:
            first += f" That may bring in about {_format_naira(expected_money)}."

    paragraphs = [first]

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
) -> dict:
    """Forecast overall and product-level sales from cleaned data."""
    forecast_periods = _normalize_forecast_periods(forecast_periods)
    working = _validate_sales_dataframe(df)
    working, _ = apply_profit_columns(working)

    monthly = prepare_monthly_totals(working)
    if len(monthly) < MIN_HISTORY_MONTHS:
        raise ForecastError(
            f"Need at least {MIN_HISTORY_MONTHS} months of sales history to forecast. "
            f"This file only has {len(monthly)} month(s)."
        )

    build_periods = max(forecast_periods, MAX_FORECAST_MONTHS)

    overall_rows, history_labels, history_units, forecast_labels, forecast_units = _build_forecast_rows(
        monthly,
        "quantity",
        build_periods,
        round_as_int=True,
    )

    has_money = "money_made" in monthly.columns
    has_profit = "profit" in monthly.columns
    history_money: list[float] | None = None
    forecast_money: list[float] | None = None
    history_profit: list[float] | None = None
    forecast_profit: list[float] | None = None

    if has_money:
        money_rows, _, history_money, _, forecast_money = _build_forecast_rows(
            monthly,
            "money_made",
            build_periods,
            round_as_int=False,
        )
        for overall, money in zip(overall_rows, money_rows):
            overall["predicted_money"] = money["predicted_money"]

    if has_profit:
        profit_rows, _, history_profit, _, forecast_profit = _build_forecast_rows(
            monthly,
            "profit",
            build_periods,
            round_as_int=False,
        )
        for overall, profit in zip(overall_rows, profit_rows):
            overall["predicted_profit"] = profit["predicted_money"]

    loss_products: set[str] = set()
    if has_profit:
        product_profit = working.groupby("product")["profit"].sum()
        loss_products = set(product_profit[product_profit < 0].index.tolist())

    product_forecasts = _build_product_forecast_rows(working, forecast_periods, loss_products)
    stock_groups = _build_stock_groups(product_forecasts)
    confidence = _forecast_confidence(len(monthly))

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
    top_product = product_forecasts[0]["product"] if product_forecasts else "—"

    last_history_units = int(history_units[-1])
    first_forecast_units = int(forecast_units[0])
    overall_trend = _trend_label(last_history_units, first_forecast_units)

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
    )

    return {
        "history_months": len(monthly),
        "forecast_periods": forecast_periods,
        "forecast_period_label": _period_label_text(forecast_periods),
        "forecast_months": forecast_periods,
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
            "product_filter": "All products",
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


def forecast_sales_file(
    filepath: Path,
    forecast_periods: int = DEFAULT_FORECAST_PERIOD,
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
        report = forecast_sales_dataframe(df, forecast_periods=forecast_periods)
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
