from pathlib import Path

import pandas as pd
import pytest

from logic.data_cleaner import DataCleaningError, clean_sales_dataframe, map_columns


def test_map_columns_recognises_common_aliases():
    rename_map, unmapped = map_columns(["Date", "Product Name", "Qty", "Notes"])
    assert rename_map["Date"] == "sale_date"
    assert rename_map["Product Name"] == "product"
    assert rename_map["Qty"] == "quantity"
    assert unmapped == ["Notes"]


def test_clean_sales_dataframe_removes_bad_rows_and_duplicates():
    raw = pd.DataFrame(
        {
            "Date": ["2024-01-01", "2024-01-01", "bad-date", "2024-01-02", "2024-01-03"],
            "Product": [" Panel A ", "Panel A", "Panel B", "", "Panel C"],
            "Qty": [10, 10, 5, 3, 2],
            "Price": [100, 100, 50, 20, 10],
        }
    )

    cleaned, report = clean_sales_dataframe(raw)

    assert len(cleaned) == 2
    assert list(cleaned["product"]) == ["Panel A", "Panel C"]
    assert report["issues_fixed"]["duplicates_removed"] == 1
    assert report["issues_fixed"]["invalid_dates_removed"] == 1
    assert report["issues_fixed"]["non_positive_quantity_removed"] == 1
    assert "unit_price" in cleaned.columns
    assert "total_amount" in cleaned.columns


def test_clean_sales_dataframe_requires_core_columns():
    raw = pd.DataFrame({"Date": ["2024-01-01"], "Notes": ["test"]})

    with pytest.raises(DataCleaningError, match="required column"):
        clean_sales_dataframe(raw)


def test_clean_sales_file_writes_csv(tmp_path: Path):
    source = tmp_path / "sales.xlsx"
    output = tmp_path / "cleaned"

    pd.DataFrame(
        {
            "Order Date": ["2024-03-01", "2024-03-02"],
            "Item": ["Inverter", "Battery"],
            "Units Sold": [2, 5],
            "Amount": [4000, 7500],
        }
    ).to_excel(source, index=False)

    from logic.data_cleaner import clean_sales_file

    report = clean_sales_file(source, output)

    assert report["success"] is True
    assert (output / "sales_cleaned.csv").exists()
    assert report["cleaned_rows"] == 2


def test_clean_sales_dataframe_calculates_profit_when_missing():
    raw = pd.DataFrame(
        {
            "Date": ["2025-01-08"],
            "Product": ["Spark"],
            "Quantity Sold": [4],
            "Unit Price": [80_000],
            "Total Sales": [320_000],
        }
    )

    cleaned, report = clean_sales_dataframe(raw)

    assert cleaned.loc[0, "profit"] == 128_000
    assert cleaned.loc[0, "profit_margin"] == 40.0
    assert report["profit"]["used_mock_unit_costs"] is True


def test_clean_sales_dataframe_maps_unit_cost_separately_from_unit_price():
    rename_map, _ = map_columns(["Unit Price", "Unit Cost"])
    assert rename_map["Unit Price"] == "unit_price"
    assert rename_map["Unit Cost"] == "unit_cost"
