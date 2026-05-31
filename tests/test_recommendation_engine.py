from pathlib import Path

import pandas as pd
import pytest

from logic.recommendation_engine import (
    StockAdviceError,
    generate_stock_advice_dataframe,
    generate_stock_advice_file,
)


def _stock_sales_df() -> pd.DataFrame:
    rows = []
    for month in range(1, 7):
        period = f"2025-{month:02d}-15"
        rows.append(
            {
                "sale_date": period,
                "product": "Spark",
                "quantity": 10 + month,
                "unit_price": 80_000,
                "total_amount": (10 + month) * 80_000,
                "unit_cost": 48_000,
            }
        )
        rows.append(
            {
                "sale_date": period,
                "product": "JET PRO",
                "quantity": 8 + month,
                "unit_price": 35_000,
                "total_amount": (8 + month) * 35_000,
                "unit_cost": 22_000,
            }
        )
        rows.append(
            {
                "sale_date": period,
                "product": "POWERFLO 200",
                "quantity": 2,
                "unit_price": 2_600_000,
                "total_amount": 5_200_000,
                "unit_cost": 1_950_000,
            }
        )
    return pd.DataFrame(rows)


def test_generate_stock_advice_dataframe_priority_and_suggestions():
    report = generate_stock_advice_dataframe(_stock_sales_df())

    assert report["summary"]["products_with_advice"] == 3
    assert report["summary"]["total_suggested_units"] > 0
    assert report["priority_restock"]
    assert report["recommendations"][0]["suggested_stock"] > 0
    assert report["recommendations"][0]["advice_label"]
    assert "suggested_stock" in report["charts"]


def test_loss_making_product_gets_review_advice():
    df = _stock_sales_df()
    loss_row = df[df["product"] == "POWERFLO 200"].copy()
    loss_row["unit_price"] = 1_000_000
    loss_row["total_amount"] = 2_000_000
    df = pd.concat([df[df["product"] != "POWERFLO 200"], loss_row], ignore_index=True)

    report = generate_stock_advice_dataframe(df)
    powerflo = next(row for row in report["recommendations"] if row["product"] == "POWERFLO 200")

    assert powerflo["advice_label"] == "Review before restocking"
    assert powerflo["priority"] == "low"


def test_generate_stock_advice_file_reads_csv(tmp_path: Path):
    csv_path = tmp_path / "sales_cleaned.csv"
    _stock_sales_df().to_csv(csv_path, index=False)

    report = generate_stock_advice_file(csv_path)

    assert report["success"] is True
    assert report["source_file"] == "sales_cleaned.csv"


def test_generate_stock_advice_file_missing_path(tmp_path: Path):
    report = generate_stock_advice_file(tmp_path / "missing.csv")

    assert report["success"] is False
