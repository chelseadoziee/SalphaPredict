"""Derive sales insights from cleaned SalphaPredict datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from logic.data_cleaner import REQUIRED_COLUMNS

TOP_PRODUCT_LIMIT = 10
LOW_VOLUME_LIMIT = 5
HIGH_VALUE_LOW_VOLUME_LIMIT = 5
TREND_STABLE_BAND = 0.05


class SalesAnalysisError(Exception):
    """Raised when cleaned sales data cannot be analysed."""


def _validate_sales_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        raise SalesAnalysisError("No sales data available to analyse.")

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise SalesAnalysisError(
            f"Cleaned data is missing required column(s): {', '.join(missing)}."
        )

    working = df.copy()
    working["sale_date"] = pd.to_datetime(working["sale_date"], errors="coerce")
    working["quantity"] = pd.to_numeric(working["quantity"], errors="coerce")

    if "total_amount" in working.columns:
        working["total_amount"] = pd.to_numeric(working["total_amount"], errors="coerce")

    working = working.dropna(subset=["sale_date", "product", "quantity"])
    working = working[working["quantity"] > 0]

    if working.empty:
        raise SalesAnalysisError("No valid sales rows remain for analysis.")

    return working


def _round_number(value: float | int | None, places: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), places)


def _product_rows(summary: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, row in summary.iterrows():
        entry = {
            "product": row["product"],
            "quantity": int(row["quantity"]),
            "quantity_share_pct": _round_number(row["quantity_share_pct"]),
        }
        if "revenue" in summary.columns:
            entry["revenue"] = (
                _round_number(row["revenue"]) if pd.notna(row["revenue"]) else None
            )
            entry["revenue_share_pct"] = (
                _round_number(row["revenue_share_pct"])
                if pd.notna(row.get("revenue_share_pct"))
                else None
            )
        rows.append(entry)
    return rows


def get_product_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate quantity and revenue by product with share percentages."""
    grouped = (
        df.groupby("product", as_index=False)
        .agg(quantity=("quantity", "sum"))
        .sort_values("quantity", ascending=False)
    )

    total_units = grouped["quantity"].sum()
    grouped["quantity_share_pct"] = grouped["quantity"] / total_units * 100

    if "total_amount" in df.columns:
        revenue = df.groupby("product")["total_amount"].sum().reset_index(name="revenue")
        grouped = grouped.merge(revenue, on="product", how="left")
        total_revenue = grouped["revenue"].sum()
        if total_revenue > 0:
            grouped["revenue_share_pct"] = grouped["revenue"] / total_revenue * 100
        else:
            grouped["revenue_share_pct"] = 0.0
    else:
        grouped["revenue"] = None
        grouped["revenue_share_pct"] = None

    return grouped


def get_total_units(df: pd.DataFrame) -> int:
    return int(df["quantity"].sum())


def get_total_revenue(df: pd.DataFrame) -> float | None:
    if "total_amount" not in df.columns:
        return None
    return _round_number(df["total_amount"].sum())


def get_top_products_by_quantity(
    df: pd.DataFrame,
    limit: int = TOP_PRODUCT_LIMIT,
) -> list[dict]:
    summary = get_product_summary(df).sort_values("quantity", ascending=False)
    return _product_rows(summary.head(limit))


def get_revenue_by_product(
    df: pd.DataFrame,
    limit: int = TOP_PRODUCT_LIMIT,
) -> list[dict]:
    if "total_amount" not in df.columns:
        return []

    summary = get_product_summary(df).sort_values("revenue", ascending=False)
    return _product_rows(summary.head(limit))


def get_product_overview(df: pd.DataFrame) -> list[dict]:
    """All products with sold units and money made in one ranked list."""
    summary = get_product_summary(df).sort_values("quantity", ascending=False)
    return _product_rows(summary)


def get_low_volume_products(
    df: pd.DataFrame,
    limit: int = LOW_VOLUME_LIMIT,
) -> list[dict]:
    summary = get_product_summary(df).sort_values("quantity", ascending=True)
    return _product_rows(summary.head(limit))


def get_high_value_low_volume_products(
    df: pd.DataFrame,
    limit: int = HIGH_VALUE_LOW_VOLUME_LIMIT,
) -> list[dict]:
    """
    Products with below-median unit sales but above-median revenue.

    These are premium items that should not be treated as weak performers
    based on quantity alone.
    """
    if "total_amount" not in df.columns:
        return []

    summary = get_product_summary(df)
    if len(summary) < 2:
        return []

    quantity_median = summary["quantity"].median()
    revenue_median = summary["revenue"].median()

    premium = summary[
        (summary["quantity"] <= quantity_median) & (summary["revenue"] >= revenue_median)
    ].sort_values("revenue", ascending=False)

    return _product_rows(premium.head(limit))


def _join_product_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _format_naira(amount: float | int | None) -> str:
    if amount is None:
        return "—"
    return f"₦{float(amount):,.2f}"


def generate_key_insight(
    top_products: list[dict],
    revenue_by_product: list[dict],
    high_value_low_volume: list[dict],
) -> list[str]:
    """Build a data-driven insight from product rankings."""
    if not top_products:
        return ["Upload and clean product data to see a key insight here."]

    paragraphs: list[str] = []
    top1 = top_products[0]

    first = (
        f"{top1['product']} is currently the strongest product by units sold, "
        f"with {top1['quantity']} units sold"
    )

    if len(top_products) >= 2:
        top2 = top_products[1]
        combined_share = (top1.get("quantity_share_pct") or 0) + (
            top2.get("quantity_share_pct") or 0
        )
        first += f", followed closely by {top2['product']} with {top2['quantity']} units"
        if combined_share >= 50:
            first += (
                ". Together, these two products make up more than half of all "
                "products sold"
            )
        else:
            share_text = int(combined_share) if combined_share == int(combined_share) else combined_share
            first += f". Together, they make up {share_text}% of all products sold"
        first += (
            ", showing that Salpha's most popular products are driving the "
            "highest customer activity."
        )
    else:
        first += ", making it the clear leader in this dataset."

    paragraphs.append(first)

    if revenue_by_product:
        revenue_leader = revenue_by_product[0]
        premium = None
        for candidate in high_value_low_volume:
            if candidate["product"] != top1["product"]:
                premium = candidate
                break
        if premium is None and high_value_low_volume:
            premium = high_value_low_volume[0]

        if premium and premium["product"] != top1["product"]:
            second = (
                f"However, {premium['product']} tells a different story. It sold only "
                f"{premium['quantity']} units, making it one of the lower-selling "
                "products by quantity"
            )
            if premium.get("revenue") is not None:
                second += f", but it generated {_format_naira(premium['revenue'])}"
                if premium["product"] == revenue_leader["product"]:
                    second += ", which makes it the strongest product by money made."
                else:
                    second += (
                        f". {revenue_leader['product']} still made the most money overall "
                        f"at {_format_naira(revenue_leader['revenue'])}."
                    )
            second += (
                f" This means {premium['product']} should not be treated as a weak "
                "product just because it sells less often."
            )
            paragraphs.append(second)
        elif revenue_leader["product"] != top1["product"]:
            paragraphs.append(
                f"However, {revenue_leader['product']} made the most money in this dataset, "
                f"with {_format_naira(revenue_leader['revenue'])}, even though it did not "
                "sell the most units. High sales and high money made are not always the same."
            )

    fast_moving = [row["product"] for row in top_products[:2]]
    if len(fast_moving) >= 2:
        restock_text = (
            f"{_join_product_names(fast_moving)} are fast-moving products that may "
            "need regular restocking"
        )
    else:
        restock_text = (
            f"{fast_moving[0]} is a fast-moving product that may need regular restocking"
        )

    high_value_names = [row["product"] for row in high_value_low_volume[:2]]
    if high_value_names:
        track_text = (
            f"{_join_product_names(high_value_names)} "
            f"{'is' if len(high_value_names) == 1 else 'are'} high-value products that "
            "need careful tracking because each sale has a much bigger financial impact"
        )
        third = (
            f"Overall, the dashboard shows two important product groups: {restock_text}, "
            f"while {track_text}."
        )
    elif revenue_by_product and revenue_by_product[0]["product"] not in fast_moving:
        third = (
            f"Overall, the dashboard shows two important product groups: {restock_text}, "
            f"while {revenue_by_product[0]['product']} needs careful tracking because "
            "it brings in the most money."
        )
    else:
        third = f"Overall, {restock_text.capitalize()}."

    paragraphs.append(third)
    return paragraphs


def generate_dashboard_summary(
    top_products: list[dict],
    revenue_by_product: list[dict],
    high_value_low_volume: list[dict],
) -> list[str]:
    """Backward-compatible alias for key insight generation."""
    return generate_key_insight(top_products, revenue_by_product, high_value_low_volume)


def _monthly_trend(df: pd.DataFrame) -> list[dict]:
    monthly = df.copy()
    monthly["period"] = monthly["sale_date"].dt.to_period("M").astype(str)

    aggregates = {"quantity": ("quantity", "sum")}
    if "total_amount" in monthly.columns:
        aggregates["revenue"] = ("total_amount", "sum")

    trend = (
        monthly.groupby("period", as_index=False)
        .agg(**aggregates)
        .sort_values("period")
    )

    rows: list[dict] = []
    for _, row in trend.iterrows():
        entry = {
            "period": row["period"],
            "quantity": int(row["quantity"]),
        }
        if "revenue" in trend.columns:
            entry["revenue"] = _round_number(row["revenue"])
        rows.append(entry)
    return rows


def _region_breakdown(df: pd.DataFrame) -> list[dict] | None:
    if "region" not in df.columns:
        return None

    regions = df.dropna(subset=["region"]).copy()
    if regions.empty:
        return None

    aggregates = {"quantity": ("quantity", "sum")}
    if "total_amount" in regions.columns:
        aggregates["revenue"] = ("total_amount", "sum")

    grouped = (
        regions.groupby("region", as_index=False)
        .agg(**aggregates)
        .sort_values("quantity", ascending=False)
    )

    rows: list[dict] = []
    for _, row in grouped.iterrows():
        entry = {
            "region": row["region"],
            "quantity": int(row["quantity"]),
        }
        if "revenue" in grouped.columns:
            entry["revenue"] = _round_number(row["revenue"])
        rows.append(entry)
    return rows


def _trend_direction(monthly_trend: list[dict]) -> dict:
    if len(monthly_trend) < 2:
        return {
            "direction": "insufficient_data",
            "label": "Not enough data yet",
            "change_pct": None,
        }

    previous = monthly_trend[-2]["quantity"]
    latest = monthly_trend[-1]["quantity"]

    if previous == 0:
        change_pct = None
        direction = "up" if latest > 0 else "stable"
    else:
        change_pct = _round_number((latest - previous) / previous * 100)
        if change_pct is not None and change_pct > TREND_STABLE_BAND * 100:
            direction = "up"
        elif change_pct is not None and change_pct < -TREND_STABLE_BAND * 100:
            direction = "down"
        else:
            direction = "stable"

    labels = {
        "up": "Sales going up",
        "down": "Sales going down",
        "stable": "Sales staying about the same",
        "insufficient_data": "Not enough data yet",
    }
    return {
        "direction": direction,
        "label": labels[direction],
        "change_pct": change_pct,
        "latest_period": monthly_trend[-1]["period"],
        "previous_period": monthly_trend[-2]["period"],
    }


def _build_charts(
    top_products: list[dict],
    revenue_by_product: list[dict],
    monthly_trend: list[dict],
    region_breakdown: list[dict] | None,
) -> dict:
    charts = {
        "monthly_trend": {
            "labels": [row["period"] for row in monthly_trend],
            "quantity": [row["quantity"] for row in monthly_trend],
            "revenue": [row.get("revenue") for row in monthly_trend],
        },
        "top_products": {
            "labels": [row["product"] for row in top_products],
            "quantity": [row["quantity"] for row in top_products],
        },
    }

    if revenue_by_product:
        charts["revenue_by_product"] = {
            "labels": [row["product"] for row in revenue_by_product],
            "revenue": [row["revenue"] for row in revenue_by_product],
        }

    if region_breakdown:
        charts["regions"] = {
            "labels": [row["region"] for row in region_breakdown],
            "quantity": [row["quantity"] for row in region_breakdown],
        }

    return charts


def analyse_sales_dataframe(df: pd.DataFrame) -> dict:
    """Compute summary metrics and rankings from cleaned sales data."""
    working = _validate_sales_dataframe(df)

    product_summary = get_product_summary(working)
    total_units = get_total_units(working)
    total_revenue = get_total_revenue(working)

    date_min = working["sale_date"].min()
    date_max = working["sale_date"].max()
    day_span = max((date_max - date_min).days + 1, 1)

    top_products = get_top_products_by_quantity(working)
    revenue_by_product = get_revenue_by_product(working)
    product_overview = get_product_overview(working)
    high_value_products = get_high_value_low_volume_products(working)

    monthly_trend = _monthly_trend(working)
    region_breakdown = _region_breakdown(working)
    trend = _trend_direction(monthly_trend)

    top_three_share = _round_number(product_summary.head(3)["quantity_share_pct"].sum())
    key_insight = generate_key_insight(
        top_products,
        revenue_by_product,
        high_value_products,
    )

    return {
        "date_range": {
            "start": date_min.strftime("%Y-%m-%d"),
            "end": date_max.strftime("%Y-%m-%d"),
        },
        "summary": {
            "total_units": total_units,
            "total_revenue": total_revenue,
            "unique_products": int(product_summary.shape[0]),
            "transaction_count": int(len(working)),
            "avg_daily_units": _round_number(total_units / day_span),
            "unique_regions": (
                int(working["region"].nunique()) if "region" in working.columns else None
            ),
            "top_three_share_pct": top_three_share,
        },
        "key_insight": key_insight,
        "dashboard_summary": key_insight,
        "demand_trend": trend,
        "top_products": top_products,
        "revenue_by_product": revenue_by_product,
        "product_overview": product_overview,
        "high_value_products": high_value_products,
        "high_value_low_volume_products": high_value_products,
        "monthly_trend": monthly_trend,
        "region_breakdown": region_breakdown,
        "charts": _build_charts(
            top_products,
            revenue_by_product,
            monthly_trend,
            region_breakdown,
        ),
    }


def analyse_sales_file(filepath: Path) -> dict:
    """Load a cleaned CSV file and return a UI-friendly analysis report."""
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
        report = analyse_sales_dataframe(df)
    except SalesAnalysisError as exc:
        return {
            "success": False,
            "error": str(exc),
        }

    return {
        "success": True,
        "source_file": filepath.name,
        **report,
    }
