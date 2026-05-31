"""Derive profit and loss insights from cleaned SalphaPredict datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from logic.mock_costs import MOCK_COST_DISCLAIMER, apply_profit_columns
from logic.sales_analyser import SalesAnalysisError, _round_number, _validate_sales_dataframe

TOP_PRODUCT_LIMIT = 10
HIGH_MARGIN_LIMIT = 5
LOSS_PRODUCT_LIMIT = 5


class ProfitAnalysisError(Exception):
    """Raised when cleaned sales data cannot be analysed for profit and loss."""


def _format_naira(amount: float | None) -> str:
    if amount is None or pd.isna(amount):
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


def _prepare_profit_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    working = _validate_sales_dataframe(df)
    working, profit_meta = apply_profit_columns(working)

    if working["profit"].notna().sum() == 0:
        raise ProfitAnalysisError(
            "No profit or loss data is available. Add Unit Cost to your upload, or use "
            "products with known mock cost estimates."
        )

    return working, profit_meta


def get_product_profit_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate money made, cost, profit, and loss by product."""
    with_results = df[df["profit"].notna()].copy()
    grouped = (
        with_results.groupby("product", as_index=False)
        .agg(
            money_made=("total_amount", "sum"),
            total_cost=("total_cost", "sum"),
            profit=("profit", "sum"),
            loss=("loss", "sum"),
        )
        .sort_values("profit", ascending=False)
    )

    grouped["gross_profit"] = grouped["profit"].apply(lambda value: value if value > 0 else 0.0)
    grouped["loss"] = grouped.apply(
        lambda row: row["loss"] if row["loss"] > 0 else (-row["profit"] if row["profit"] < 0 else 0.0),
        axis=1,
    )
    grouped["profit_margin_pct"] = grouped.apply(
        lambda row: (row["profit"] / row["money_made"] * 100) if row["money_made"] else 0,
        axis=1,
    )

    total_gross_profit = grouped["gross_profit"].sum()
    total_loss = grouped["loss"].sum()
    grouped["profit_share_pct"] = grouped.apply(
        lambda row: (row["gross_profit"] / total_gross_profit * 100) if total_gross_profit > 0 else 0,
        axis=1,
    )
    grouped["loss_share_pct"] = grouped.apply(
        lambda row: (row["loss"] / total_loss * 100) if total_loss > 0 else 0,
        axis=1,
    )
    return grouped


def _product_profit_rows(summary: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, row in summary.iterrows():
        rows.append(
            {
                "product": row["product"],
                "money_made": _round_number(row["money_made"]),
                "total_cost": _round_number(row["total_cost"]),
                "gross_profit": _round_number(row["gross_profit"]),
                "loss": _round_number(row["loss"]),
                "net_result": _round_number(row["profit"]),
                "profit_margin_pct": _round_number(row["profit_margin_pct"]),
                "profit_share_pct": _round_number(row["profit_share_pct"]),
                "loss_share_pct": _round_number(row["loss_share_pct"]),
            }
        )
    return rows


def _monthly_profit_trend(df: pd.DataFrame) -> list[dict]:
    with_results = df[df["profit"].notna()].copy()
    with_results["period"] = with_results["sale_date"].dt.to_period("M").astype(str)

    trend = (
        with_results.groupby("period", as_index=False)
        .agg(
            money_made=("total_amount", "sum"),
            total_cost=("total_cost", "sum"),
            profit=("profit", "sum"),
            loss=("loss", "sum"),
        )
        .sort_values("period")
    )

    rows: list[dict] = []
    for _, row in trend.iterrows():
        gross_profit = row["profit"] if row["profit"] > 0 else 0.0
        loss = row["loss"] if row["loss"] > 0 else (-row["profit"] if row["profit"] < 0 else 0.0)
        margin = (row["profit"] / row["money_made"] * 100) if row["money_made"] else 0
        rows.append(
            {
                "period": row["period"],
                "money_made": _round_number(row["money_made"]),
                "total_cost": _round_number(row["total_cost"]),
                "gross_profit": _round_number(gross_profit),
                "loss": _round_number(loss),
                "net_result": _round_number(row["profit"]),
                "profit_margin_pct": _round_number(margin),
            }
        )
    return rows


def generate_profit_insight(
    summary: dict,
    top_by_profit: list[dict],
    top_by_margin: list[dict],
    loss_making_products: list[dict],
) -> list[str]:
    paragraphs = [
        (
            f"Across this dataset, SalphaPredict recorded "
            f"{_format_naira(summary['total_gross_profit'])} in gross profit and "
            f"{_format_naira(summary['total_loss'])} in total loss, "
            f"giving a net result of {_format_naira(summary['net_result'])} "
            f"from {_format_naira(summary['total_money_made'])} in money made."
        )
    ]

    if top_by_profit:
        leader = top_by_profit[0]
        if len(top_by_profit) >= 2:
            second = top_by_profit[1]
            paragraphs.append(
                f"{leader['product']} led gross profit at "
                f"{_format_naira(leader['gross_profit'])}, followed by "
                f"{second['product']} at {_format_naira(second['gross_profit'])}."
            )
        else:
            paragraphs.append(
                f"{leader['product']} led gross profit at "
                f"{_format_naira(leader['gross_profit'])}."
            )

    if loss_making_products:
        loss_names = [row["product"] for row in loss_making_products[:3]]
        paragraphs.append(
            f"Some products made a loss, including {_join_product_names(loss_names)}. "
            f"{loss_making_products[0]['product']} had the largest loss at "
            f"{_format_naira(loss_making_products[0]['loss'])}. "
            "These are worth reviewing for pricing or cost issues."
        )
    elif top_by_margin:
        margin_leader = top_by_margin[0]
        paragraphs.append(
            f"{margin_leader['product']} had the strongest profit margin "
            f"at {margin_leader['profit_margin_pct']}% among products with profit data."
        )

    return paragraphs


def _build_charts(
    monthly_trend: list[dict],
    top_by_profit: list[dict],
    loss_making_products: list[dict],
) -> dict:
    charts = {
        "monthly_profit_and_loss": {
            "labels": [row["period"] for row in monthly_trend],
            "gross_profit": [row["gross_profit"] for row in monthly_trend],
            "loss": [row["loss"] for row in monthly_trend],
            "net_result": [row["net_result"] for row in monthly_trend],
        },
        "monthly_money_and_cost": {
            "labels": [row["period"] for row in monthly_trend],
            "money_made": [row["money_made"] for row in monthly_trend],
            "total_cost": [row["total_cost"] for row in monthly_trend],
        },
        "profit_by_product": {
            "labels": [row["product"] for row in top_by_profit if (row["gross_profit"] or 0) > 0],
            "profit": [row["gross_profit"] for row in top_by_profit if (row["gross_profit"] or 0) > 0],
        },
    }

    if loss_making_products:
        charts["loss_by_product"] = {
            "labels": [row["product"] for row in loss_making_products],
            "loss": [row["loss"] for row in loss_making_products],
        }

    return charts


def analyse_profit_dataframe(df: pd.DataFrame) -> dict:
    """Compute profit and loss metrics from cleaned sales data."""
    working, profit_meta = _prepare_profit_dataframe(df)
    with_results = working[working["profit"].notna()].copy()

    product_summary = get_product_profit_summary(with_results)
    product_rows = _product_profit_rows(product_summary)

    total_money_made = _round_number(with_results["total_amount"].sum())
    total_cost = _round_number(with_results["total_cost"].sum())
    total_gross_profit = _round_number(with_results.loc[with_results["profit"] > 0, "profit"].sum())
    total_loss = _round_number(with_results.loc[with_results["profit"] < 0, "loss"].sum())
    net_result = _round_number(with_results["profit"].sum())
    overall_margin = (
        _round_number(net_result / total_money_made * 100) if total_money_made else None
    )

    profitable_products = [
        row for row in product_rows if (row["gross_profit"] or 0) > 0
    ]
    top_by_profit = sorted(
        profitable_products,
        key=lambda row: row["gross_profit"] or 0,
        reverse=True,
    )[:TOP_PRODUCT_LIMIT]

    loss_making_products = sorted(
        [row for row in product_rows if (row["loss"] or 0) > 0],
        key=lambda row: row["loss"] or 0,
        reverse=True,
    )[:LOSS_PRODUCT_LIMIT]

    top_by_margin = sorted(
        product_rows,
        key=lambda row: row["profit_margin_pct"] or 0,
        reverse=True,
    )[:HIGH_MARGIN_LIMIT]

    monthly_trend = _monthly_profit_trend(with_results)
    date_min = with_results["sale_date"].min()
    date_max = with_results["sale_date"].max()

    summary = {
        "total_money_made": total_money_made,
        "total_cost": total_cost,
        "total_gross_profit": total_gross_profit,
        "total_loss": total_loss,
        "net_result": net_result,
        "overall_profit_margin_pct": overall_margin,
        "products_with_profit_data": int(product_summary.shape[0]),
        "loss_making_products": len([row for row in product_rows if (row["loss"] or 0) > 0]),
        "rows_with_profit_data": int(len(with_results)),
        "rows_with_loss": int((with_results["loss"].fillna(0) > 0).sum()),
        "rows_missing_profit": int(working["profit"].isna().sum()),
    }

    return {
        "date_range": {
            "start": date_min.strftime("%Y-%m-%d"),
            "end": date_max.strftime("%Y-%m-%d"),
        },
        "summary": summary,
        "profit_meta": profit_meta,
        "used_mock_unit_costs": profit_meta.get("used_mock_unit_costs", False),
        "mock_cost_disclaimer": MOCK_COST_DISCLAIMER if profit_meta.get("used_mock_unit_costs") else None,
        "profit_insight": generate_profit_insight(
            summary,
            top_by_profit,
            top_by_margin,
            loss_making_products,
        ),
        "product_profit_overview": product_rows,
        "top_profit_products": top_by_profit,
        "loss_making_products": loss_making_products,
        "highest_margin_products": top_by_margin,
        "monthly_profit_trend": monthly_trend,
        "charts": _build_charts(monthly_trend, top_by_profit, loss_making_products),
    }


def analyse_profit_file(filepath: Path) -> dict:
    """Load a cleaned CSV file and return a UI-friendly profit and loss report."""
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
        report = analyse_profit_dataframe(df)
    except (ProfitAnalysisError, SalesAnalysisError) as exc:
        return {
            "success": False,
            "error": str(exc),
        }

    return {
        "success": True,
        "source_file": filepath.name,
        **report,
    }
