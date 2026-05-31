"""Mock unit costs and profit helpers for SalphaPredict prototype datasets.

IMPORTANT: Unit cost values below are estimated mock figures for prototype
testing only. They are NOT real Salpha Energy cost data and must not be used
for actual financial or procurement decisions.
"""

from __future__ import annotations

import pandas as pd

MOCK_COST_DISCLAIMER = (
    "Unit cost values in SalphaPredict mock datasets are estimated prototype "
    "figures only — not real Salpha Energy cost data."
)

# Estimated mock unit costs (NGN) by product name — prototype testing only.
MOCK_UNIT_COSTS: dict[str, float] = {
    "JET PRO": 22_000,
    "Spark": 48_000,
    "WIND MASTER": 85_000,
    "WIND MASTER PRO": 92_000,
    "POWERFLO 30": 310_000,
    "POWERFLO 100": 720_000,
    "POWERFLO 200": 1_950_000,
}

# Mock product categories for the Excel sample file (not used in cleaning yet).
MOCK_PRODUCT_CATEGORIES: dict[str, str] = {
    "JET PRO": "Inverter",
    "Spark": "Inverter",
    "WIND MASTER": "Wind Turbine",
    "WIND MASTER PRO": "Wind Turbine",
    "POWERFLO 30": "Battery Storage",
    "POWERFLO 100": "Battery Storage",
    "POWERFLO 200": "Battery Storage",
}

EXCEL_COLUMN_ORDER = (
    "Date",
    "Product",
    "Category",
    "Quantity Sold",
    "Unit Price",
    "Total Sales",
    "Unit Cost",
    "Total Cost",
    "Profit",
    "Profit Margin",
)


class MockCostError(Exception):
    """Raised when mock profit columns cannot be calculated."""


def get_mock_unit_cost(product: str) -> float:
    """Return the mock unit cost for a product, or raise if unknown."""
    normalized = str(product).strip()
    if normalized not in MOCK_UNIT_COSTS:
        known = ", ".join(sorted(MOCK_UNIT_COSTS))
        raise MockCostError(
            f"No mock unit cost defined for product '{normalized}'. "
            f"Known products: {known}."
        )
    return MOCK_UNIT_COSTS[normalized]


def get_mock_category(product: str) -> str:
    """Return the mock category label for a product."""
    normalized = str(product).strip()
    return MOCK_PRODUCT_CATEGORIES.get(normalized, "Uncategorised")


def calculate_profit_row(
    quantity: float,
    unit_price: float,
    unit_cost: float,
) -> dict[str, float]:
    """Calculate Total Sales, Total Cost, Profit, and Profit Margin for one row."""
    qty = float(quantity)
    total_sales = qty * float(unit_price)
    total_cost = qty * float(unit_cost)
    profit = total_sales - total_cost
    profit_margin = (profit / total_sales * 100) if total_sales else 0.0
    return {
        "Total Sales": round(total_sales, 2),
        "Total Cost": round(total_cost, 2),
        "Profit": round(profit, 2),
        "Profit Margin": round(profit_margin, 2),
    }


def _round_profit_value(value: float | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 2)


def apply_profit_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Add or fill profit-related columns on cleaned sales data.

    Uses values from the upload when present. Missing fields are calculated as:
    - total_amount from quantity × unit_price (if needed)
    - unit_cost from the file, or mock estimates for known products
    - total_cost = quantity × unit_cost
    - profit = total_amount − total_cost
    - profit_margin = (profit / total_amount) × 100
    """
    working = df.copy()
    report: dict = {
        "used_mock_unit_costs": False,
        "rows_with_profit": 0,
        "rows_missing_profit": 0,
    }

    if "total_amount" not in working.columns and "unit_price" in working.columns:
        working["total_amount"] = working["unit_price"] * working["quantity"]

    if "total_amount" not in working.columns:
        return working, report

    for column in ("unit_cost", "total_cost", "profit", "profit_margin"):
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")

    if "unit_cost" not in working.columns:
        working["unit_cost"] = pd.NA

    missing_unit_cost = working["unit_cost"].isna()
    if missing_unit_cost.any():
        mock_values = working.loc[missing_unit_cost, "product"].map(
            lambda name: MOCK_UNIT_COSTS.get(str(name).strip(), pd.NA)
        )
        if mock_values.notna().any():
            report["used_mock_unit_costs"] = True
        working.loc[missing_unit_cost, "unit_cost"] = mock_values

    if "total_cost" not in working.columns:
        working["total_cost"] = pd.NA

    missing_total_cost = working["total_cost"].isna() & working["unit_cost"].notna()
    working.loc[missing_total_cost, "total_cost"] = (
        working.loc[missing_total_cost, "quantity"] * working.loc[missing_total_cost, "unit_cost"]
    )

    if "profit" not in working.columns:
        working["profit"] = pd.NA

    missing_profit = (
        working["profit"].isna()
        & working["total_amount"].notna()
        & working["total_cost"].notna()
    )
    working.loc[missing_profit, "profit"] = (
        working.loc[missing_profit, "total_amount"] - working.loc[missing_profit, "total_cost"]
    )

    if "profit_margin" not in working.columns:
        working["profit_margin"] = pd.NA

    missing_margin = (
        working["profit_margin"].isna()
        & working["profit"].notna()
        & working["total_amount"].notna()
        & (working["total_amount"] > 0)
    )
    working.loc[missing_margin, "profit_margin"] = (
        working.loc[missing_margin, "profit"] / working.loc[missing_margin, "total_amount"] * 100
    )

    if "loss" not in working.columns:
        working["loss"] = pd.NA

    has_result = working["profit"].notna()
    working.loc[has_result, "loss"] = working.loc[has_result, "profit"].apply(
        lambda value: -float(value) if float(value) < 0 else 0.0
    )

    for column in ("unit_cost", "total_cost", "profit", "profit_margin", "loss", "total_amount"):
        if column in working.columns:
            working[column] = working[column].apply(_round_profit_value)

    report["rows_with_profit"] = int(working["profit"].notna().sum())
    report["rows_missing_profit"] = int(working["profit"].isna().sum())
    report["rows_with_loss"] = int((working["loss"].fillna(0) > 0).sum())
    return working, report


def build_mock_excel_dataframe(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    """Turn cleaned sales rows into an Excel-ready mock file with profit columns."""
    required = {"sale_date", "product", "quantity", "unit_price"}
    missing = required - set(cleaned_df.columns)
    if missing:
        raise MockCostError(
            f"Cleaned data is missing required column(s): {', '.join(sorted(missing))}."
        )

    rows: list[dict] = []
    for _, record in cleaned_df.iterrows():
        product = str(record["product"]).strip()
        quantity = float(record["quantity"])
        unit_price = float(record["unit_price"])
        unit_cost = get_mock_unit_cost(product)
        profit_values = calculate_profit_row(quantity, unit_price, unit_cost)

        rows.append(
            {
                "Date": pd.to_datetime(record["sale_date"]).strftime("%Y-%m-%d"),
                "Product": product,
                "Category": get_mock_category(product),
                "Quantity Sold": int(quantity) if quantity == int(quantity) else quantity,
                "Unit Price": unit_price,
                "Unit Cost": unit_cost,
                **profit_values,
            }
        )

    return pd.DataFrame(rows, columns=list(EXCEL_COLUMN_ORDER))
