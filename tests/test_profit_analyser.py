from pathlib import Path

import pandas as pd
import pytest

from logic.profit_analyser import ProfitAnalysisError, analyse_profit_dataframe, analyse_profit_file


def _profit_sales_df() -> pd.DataFrame:
    rows = []
    for month in range(1, 5):
        period = f"2025-{month:02d}-15"
        rows.append(
            {
                "sale_date": period,
                "product": "Spark",
                "quantity": 4,
                "unit_price": 80_000,
                "total_amount": 320_000,
                "unit_cost": 48_000,
            }
        )
        rows.append(
            {
                "sale_date": period,
                "product": "JET PRO",
                "quantity": 6,
                "unit_price": 35_000,
                "total_amount": 210_000,
                "unit_cost": 22_000,
            }
        )
    return pd.DataFrame(rows)


def test_analyse_profit_dataframe_summary_and_rankings():
    report = analyse_profit_dataframe(_profit_sales_df())

    assert report["summary"]["net_result"] == 824_000
    assert report["summary"]["total_gross_profit"] == 824_000
    assert report["summary"]["total_loss"] == 0
    assert report["top_profit_products"][0]["product"] == "Spark"
    assert report["product_profit_overview"][0]["profit_margin_pct"] == 40.0
    assert report["loss_making_products"] == []
    assert "monthly_profit_and_loss" in report["charts"]


def test_analyse_profit_dataframe_calculates_loss():
    df = pd.DataFrame(
        {
            "sale_date": ["2025-01-01", "2025-01-02"],
            "product": ["Spark", "Discount Panel"],
            "quantity": [4, 2],
            "unit_price": [80_000, 30_000],
            "total_amount": [320_000, 60_000],
            "unit_cost": [48_000, 50_000],
        }
    )

    report = analyse_profit_dataframe(df)

    assert report["summary"]["total_gross_profit"] == 128_000
    assert report["summary"]["total_loss"] == 40_000
    assert report["summary"]["net_result"] == 88_000
    assert report["loss_making_products"][0]["product"] == "Discount Panel"
    assert report["loss_making_products"][0]["loss"] == 40_000
    assert "loss_by_product" in report["charts"]


def test_analyse_profit_dataframe_applies_mock_costs_when_missing():
    df = _profit_sales_df().drop(columns=["unit_cost"])
    report = analyse_profit_dataframe(df)

    assert report["used_mock_unit_costs"] is True
    assert report["summary"]["net_result"] > 0


def test_analyse_profit_dataframe_requires_profitable_rows():
    df = pd.DataFrame(
        {
            "sale_date": ["2025-01-01"],
            "product": ["Unknown Product"],
            "quantity": [2],
            "unit_price": [1000],
            "total_amount": [2000],
        }
    )

    with pytest.raises(ProfitAnalysisError, match="No profit or loss data"):
        analyse_profit_dataframe(df)


def test_analyse_profit_file_reads_csv(tmp_path: Path):
    csv_path = tmp_path / "sales_cleaned.csv"
    _profit_sales_df().to_csv(csv_path, index=False)

    report = analyse_profit_file(csv_path)

    assert report["success"] is True
    assert report["source_file"] == "sales_cleaned.csv"
