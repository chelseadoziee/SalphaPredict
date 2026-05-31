"""Generate practical stock advice from sales, forecast, and profit data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from logic.forecasting_engine import (
    MIN_HISTORY_MONTHS,
    ForecastError,
    _fit_linear_forecast,
    _trend_label,
    _trend_text,
    prepare_monthly_product_series,
)
from logic.mock_costs import apply_profit_columns
from logic.sales_analyser import (
    SalesAnalysisError,
    _round_number,
    _validate_sales_dataframe,
    get_high_value_low_volume_products,
    get_product_summary,
)

TOP_ADVICE_LIMIT = 15
HIGH_VOLUME_RANK = 3


class StockAdviceError(Exception):
    """Raised when stock advice cannot be generated."""


def _join_product_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _product_forecast_stats(df: pd.DataFrame, product: str) -> dict:
    monthly = prepare_monthly_product_series(df, product)
    values = [float(value) for value in monthly["quantity"].tolist()]
    month_count = len(values)
    avg_monthly = sum(values) / month_count if month_count else 0
    last_month_sold = int(values[-1]) if values else 0

    next_month_forecast = None
    trend = "insufficient_data"
    trend_label = "Not enough monthly history"

    if month_count >= MIN_HISTORY_MONTHS:
        try:
            prediction = _fit_linear_forecast(values, 1)[0]
            next_month_forecast = int(round(prediction))
            trend = _trend_label(last_month_sold, next_month_forecast)
            trend_label = _trend_text(trend)
        except ForecastError:
            next_month_forecast = int(round(avg_monthly))

    return {
        "month_count": month_count,
        "avg_monthly_sold": _round_number(avg_monthly),
        "last_month_sold": last_month_sold,
        "next_month_forecast": next_month_forecast,
        "trend": trend,
        "trend_label": trend_label,
    }


def _suggested_stock(
    last_month_sold: int,
    next_month_forecast: int | None,
    avg_monthly_sold: float | None,
    trend: str,
    is_top_seller: bool,
) -> int:
    baseline = float(next_month_forecast or avg_monthly_sold or last_month_sold or 0)
    baseline = max(baseline, float(last_month_sold))

    if trend == "up" and is_top_seller:
        buffer = 1.15
    elif trend == "up":
        buffer = 1.1
    elif trend == "down":
        buffer = 0.95
    else:
        buffer = 1.05

    return max(int(round(baseline * buffer)), 0)


def _build_advice_label(
    *,
    trend: str,
    is_top_seller: bool,
    is_high_value: bool,
    is_loss_making: bool,
) -> tuple[str, str, str]:
    """Return advice label, priority, and short reason."""
    if is_loss_making:
        return (
            "Review before restocking",
            "low",
            "Cost is higher than money made on this product.",
        )

    if is_high_value:
        return (
            "Keep small buffer",
            "medium",
            "High-value product — each sale has a bigger financial impact.",
        )

    if is_top_seller and trend == "up":
        return (
            "Restock more",
            "high",
            "Fast seller with sales forecast going up.",
        )

    if is_top_seller:
        return (
            "Keep regular stock",
            "high",
            "One of the most sold products in the dataset.",
        )

    if trend == "up":
        return (
            "Increase stock",
            "medium",
            "Sales forecast is trending up for next month.",
        )

    if trend == "down":
        return (
            "Watch before restocking",
            "low",
            "Sales forecast is trending down for next month.",
        )

    return (
        "Keep regular stock",
        "medium",
        "Sales look fairly steady based on recent months.",
    )


def generate_stock_insight(
    summary: dict,
    priority_restock: list[dict],
    watch_list: list[dict],
) -> list[str]:
    paragraphs = [
        (
            f"SalphaPredict suggests about {summary['total_suggested_units']} products "
            f"in stock across {summary['products_with_advice']} products, "
            f"based on recent sales and next-month forecasts."
        )
    ]

    if priority_restock:
        names = [row["product"] for row in priority_restock[:3]]
        paragraphs.append(
            f"Priority restocking applies to {_join_product_names(names)}. "
            f"{priority_restock[0]['product']} needs about "
            f"{priority_restock[0]['suggested_stock']} units, with advice to "
            f"{priority_restock[0]['advice_label'].lower()}."
        )

    if watch_list:
        watch_names = [row["product"] for row in watch_list[:3]]
        paragraphs.append(
            f"Watch closely before ordering more for {_join_product_names(watch_names)} — "
            "forecast or profit signals suggest a lighter stock level may be safer."
        )
    elif summary["high_value_products"]:
        hv_names = [row["product"] for row in summary["high_value_products"][:2]]
        paragraphs.append(
            f"{_join_product_names(hv_names)} "
            f"{'is' if len(hv_names) == 1 else 'are'} high-value products — "
            "keep a smaller buffer but do not treat low unit sales as weak demand."
        )

    return paragraphs


def _build_charts(recommendations: list[dict]) -> dict:
    top = sorted(recommendations, key=lambda row: row["suggested_stock"], reverse=True)[
        :TOP_ADVICE_LIMIT
    ]
    return {
        "suggested_stock": {
            "labels": [row["product"] for row in top],
            "values": [row["suggested_stock"] for row in top],
        }
    }


def generate_stock_advice_dataframe(df: pd.DataFrame) -> dict:
    """Build stock advice for each product in cleaned sales data."""
    working = _validate_sales_dataframe(df)
    product_summary = get_product_summary(working).sort_values("quantity", ascending=False)

    if product_summary.empty:
        raise StockAdviceError("No products available for stock advice.")

    high_value_names = {
        row["product"] for row in get_high_value_low_volume_products(working)
    }

    with_profit, _ = apply_profit_columns(working)
    loss_by_product: set[str] = set()
    if "profit" in with_profit.columns:
        product_profit = (
            with_profit.groupby("product")["profit"].sum().reset_index()
        )
        loss_by_product = set(
            product_profit.loc[product_profit["profit"] < 0, "product"].tolist()
        )

    recommendations: list[dict] = []
    for rank, (_, row) in enumerate(product_summary.iterrows(), start=1):
        product = row["product"]
        stats = _product_forecast_stats(working, product)
        is_top_seller = rank <= HIGH_VOLUME_RANK
        is_high_value = product in high_value_names
        is_loss_making = product in loss_by_product

        advice_label, priority, reason = _build_advice_label(
            trend=stats["trend"],
            is_top_seller=is_top_seller,
            is_high_value=is_high_value,
            is_loss_making=is_loss_making,
        )

        suggested_stock = _suggested_stock(
            last_month_sold=stats["last_month_sold"],
            next_month_forecast=stats["next_month_forecast"],
            avg_monthly_sold=stats["avg_monthly_sold"],
            trend=stats["trend"],
            is_top_seller=is_top_seller,
        )

        recommendations.append(
            {
                "product": product,
                "total_sold": int(row["quantity"]),
                "last_month_sold": stats["last_month_sold"],
                "avg_monthly_sold": stats["avg_monthly_sold"],
                "next_month_forecast": stats["next_month_forecast"],
                "suggested_stock": suggested_stock,
                "trend": stats["trend"],
                "trend_label": stats["trend_label"],
                "advice_label": advice_label,
                "priority": priority,
                "priority_label": priority.capitalize(),
                "reason": reason,
                "is_high_value": is_high_value,
            }
        )

    priority_restock = [
        row for row in recommendations if row["priority"] == "high"
    ]
    watch_list = [
        row
        for row in recommendations
        if row["priority"] == "low" or row["trend"] == "down"
    ]

    date_min = working["sale_date"].min()
    date_max = working["sale_date"].max()

    summary = {
        "products_with_advice": len(recommendations),
        "priority_restock_count": len(priority_restock),
        "watch_count": len(watch_list),
        "total_suggested_units": int(sum(row["suggested_stock"] for row in recommendations)),
        "high_value_products": [
            row for row in recommendations if row["is_high_value"]
        ],
    }

    return {
        "date_range": {
            "start": date_min.strftime("%Y-%m-%d"),
            "end": date_max.strftime("%Y-%m-%d"),
        },
        "summary": summary,
        "stock_insight": generate_stock_insight(summary, priority_restock, watch_list),
        "recommendations": recommendations,
        "priority_restock": priority_restock,
        "watch_list": watch_list,
        "charts": _build_charts(recommendations),
    }


def generate_stock_advice_file(filepath: Path) -> dict:
    """Load a cleaned CSV file and return a UI-friendly stock advice report."""
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
        report = generate_stock_advice_dataframe(df)
    except (StockAdviceError, SalesAnalysisError) as exc:
        return {
            "success": False,
            "error": str(exc),
        }

    return {
        "success": True,
        "source_file": filepath.name,
        **report,
    }
