"""Normalize and validate uploaded sales spreadsheets for downstream analysis."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from logic.mock_costs import apply_profit_columns

REQUIRED_COLUMNS = ("sale_date", "product", "quantity")
OPTIONAL_COLUMNS = (
    "category",
    "unit_price",
    "total_amount",
    "unit_cost",
    "total_cost",
    "profit",
    "profit_margin",
    "loss",
    "region",
    "customer",
)
STANDARD_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

# Common header labels found in Salpha Energy sales exports (matched after normalization).
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "sale_date": (
        "date",
        "sale date",
        "sales date",
        "order date",
        "transaction date",
        "invoice date",
        "sale_date",
    ),
    "product": (
        "product",
        "product name",
        "product_name",
        "item",
        "item name",
        "sku",
        "product code",
        "product_code",
        "description",
    ),
    "quantity": (
        "quantity",
        "qty",
        "units",
        "units sold",
        "quantity sold",
        "qty sold",
        "volume",
    ),
    "category": ("category", "product category", "product_category", "type"),
    "unit_price": (
        "unit price",
        "unit_price",
        "price",
        "selling price",
        "rate",
    ),
    "unit_cost": ("unit cost", "unit_cost", "cost per unit", "cost price"),
    "total_cost": ("total cost", "total_cost", "line cost"),
    "profit": ("profit", "gross profit"),
    "profit_margin": (
        "profit margin",
        "profit_margin",
        "margin percent",
        "margin %",
        "margin pct",
    ),
    "loss": ("loss", "total loss", "loss amount"),
    "total_amount": (
        "total",
        "amount",
        "revenue",
        "sales",
        "total sales",
        "line total",
        "total amount",
        "total_amount",
        "value",
    ),
    "region": ("region", "location", "area", "branch", "territory", "zone"),
    "customer": ("customer", "client", "buyer", "customer name", "account"),
}


class DataCleaningError(Exception):
    """Raised when a spreadsheet cannot be mapped or cleaned safely."""


def _normalize_header(name: object) -> str:
    text = str(name).strip().lower()
    text = re.sub(r"[_\-]+", " ", text)
    return re.sub(r"\s+", " ", text)


def _build_alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for standard_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            lookup[_normalize_header(alias)] = standard_name
    return lookup


_ALIAS_LOOKUP = _build_alias_lookup()


def map_columns(raw_columns: list[object]) -> tuple[dict[str, str], list[str]]:
    """Map raw spreadsheet headers to the standard SalphaPredict schema."""
    rename_map: dict[str, str] = {}
    unmapped: list[str] = []

    for column in raw_columns:
        normalized = _normalize_header(column)
        standard = _ALIAS_LOOKUP.get(normalized)
        if standard:
            rename_map[str(column)] = standard
        else:
            unmapped.append(str(column))

    return rename_map, unmapped


def _strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    for column in cleaned.columns:
        if cleaned[column].dtype == object:
            cleaned[column] = cleaned[column].apply(
                lambda value: value.strip() if isinstance(value, str) else value
            )
    return cleaned


def _normalize_products(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
    )


def clean_sales_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean a sales DataFrame in memory.

    Returns the cleaned frame and a report dictionary suitable for the UI.
    """
    original_rows = len(df)
    report: dict = {
        "original_rows": original_rows,
        "issues_fixed": {
            "empty_rows_removed": 0,
            "duplicates_removed": 0,
            "invalid_dates_removed": 0,
            "missing_required_removed": 0,
            "non_positive_quantity_removed": 0,
        },
    }

    if df.empty:
        raise DataCleaningError("The uploaded file has no data rows.")

    working = df.copy()
    working.columns = [str(column).strip() for column in working.columns]

    rename_map, unmapped_columns = map_columns(list(working.columns))
    report["columns_mapped"] = rename_map
    report["columns_ignored"] = unmapped_columns

    missing_required = [
        column for column in REQUIRED_COLUMNS if column not in rename_map.values()
    ]
    if missing_required:
        found = ", ".join(working.columns) or "(none)"
        needed = ", ".join(missing_required)
        raise DataCleaningError(
            f"Could not find required column(s): {needed}. "
            f"Columns in your file: {found}. "
            "Expected headers like Date, Product, and Quantity."
        )

    working = working.rename(columns=rename_map)

    # If the same standard name appears twice, keep the first mapped column only.
    working = working.loc[:, ~working.columns.duplicated()]

    before = len(working)
    working = working.dropna(how="all")
    report["issues_fixed"]["empty_rows_removed"] = before - len(working)

    working = _strip_strings(working)

    working["sale_date"] = pd.to_datetime(working["sale_date"], errors="coerce")
    invalid_dates = working["sale_date"].isna().sum()
    working = working[working["sale_date"].notna()]
    report["issues_fixed"]["invalid_dates_removed"] = int(invalid_dates)

    working["product"] = _normalize_products(working["product"])
    working["quantity"] = pd.to_numeric(working["quantity"], errors="coerce")

    if "category" in working.columns:
        working["category"] = working["category"].apply(
            lambda value: value.strip() if isinstance(value, str) else value
        )

    numeric_optional = (
        "unit_price",
        "total_amount",
        "unit_cost",
        "total_cost",
        "profit",
        "profit_margin",
        "loss",
    )
    for optional in numeric_optional:
        if optional in working.columns:
            working[optional] = pd.to_numeric(working[optional], errors="coerce")

    before = len(working)
    working = working[working["product"].notna() & working["quantity"].notna()]
    report["issues_fixed"]["missing_required_removed"] = before - len(working)

    before = len(working)
    working = working[working["quantity"] > 0]
    report["issues_fixed"]["non_positive_quantity_removed"] = before - len(working)

    if "unit_price" in working.columns and "total_amount" not in working.columns:
        working["total_amount"] = working["unit_price"] * working["quantity"]
    elif (
        "total_amount" in working.columns
        and "unit_price" not in working.columns
        and "quantity" in working.columns
    ):
        working["unit_price"] = working["total_amount"] / working["quantity"]

    duplicate_columns = ["sale_date", "product", "quantity"]
    if "unit_price" in working.columns:
        duplicate_columns.append("unit_price")

    before = len(working)
    working = working.drop_duplicates(subset=duplicate_columns, keep="first")
    report["issues_fixed"]["duplicates_removed"] = before - len(working)

    if working.empty:
        raise DataCleaningError(
            "No valid sales rows remain after cleaning. "
            "Check that dates, products, and quantities are filled in correctly."
        )

    working, profit_report = apply_profit_columns(working)
    report["profit"] = profit_report

    columns_to_keep = [column for column in STANDARD_COLUMNS if column in working.columns]
    working = working[columns_to_keep].copy()
    working["sale_date"] = working["sale_date"].dt.normalize()
    working = working.sort_values(["sale_date", "product"]).reset_index(drop=True)

    cleaned_rows = len(working)
    report.update(
        {
            "cleaned_rows": cleaned_rows,
            "rows_removed": original_rows - cleaned_rows,
            "standard_columns": columns_to_keep,
        }
    )

    return working, report


def _sample_rows(df: pd.DataFrame, limit: int = 5) -> list[dict]:
    sample = df.head(limit).copy()
    sample["sale_date"] = sample["sale_date"].dt.strftime("%Y-%m-%d")
    return sample.where(pd.notna(sample), None).to_dict(orient="records")


def clean_sales_file(filepath: Path, output_folder: Path) -> dict:
    """
    Read an Excel sales file, clean it, save a CSV, and return a UI-friendly report.
    """
    try:
        raw_df = pd.read_excel(filepath)
    except Exception as exc:
        return {
            "success": False,
            "filename": filepath.name,
            "error": f"Could not read the Excel file: {exc}",
        }

    try:
        cleaned_df, cleaning_report = clean_sales_dataframe(raw_df)
    except DataCleaningError as exc:
        return {
            "success": False,
            "filename": filepath.name,
            "error": str(exc),
            "original_rows": len(raw_df),
        }

    output_folder.mkdir(parents=True, exist_ok=True)
    cleaned_name = f"{filepath.stem}_cleaned.csv"
    cleaned_path = output_folder / cleaned_name
    cleaned_df.to_csv(cleaned_path, index=False)

    return {
        "success": True,
        "filename": filepath.name,
        "cleaned_filename": cleaned_name,
        "cleaned_path": str(cleaned_path),
        "sample_rows": _sample_rows(cleaned_df),
        **cleaning_report,
    }
