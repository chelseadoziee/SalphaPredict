from pathlib import Path

import pandas as pd
import pytest

from logic.forecasting_engine import (
    ForecastError,
    MIN_HISTORY_MONTHS,
    forecast_sales_dataframe,
    forecast_sales_file,
    generate_forecast_insight,
)


def _monthly_sales_df(months: int = 8) -> pd.DataFrame:
    rows = []
    for month in range(1, months + 1):
        period = f"2025-{month:02d}-15"
        rows.append(
            {
                "sale_date": period,
                "product": "Spark",
                "quantity": 20 + month,
                "total_amount": (20 + month) * 80000,
            }
        )
        rows.append(
            {
                "sale_date": period,
                "product": "JET PRO",
                "quantity": 15 + month,
                "total_amount": (15 + month) * 35000,
            }
        )
        rows.append(
            {
                "sale_date": period,
                "product": "POWERFLO 200",
                "quantity": 2,
                "total_amount": 5200000,
            }
        )
    return pd.DataFrame(rows)


def test_forecast_sales_dataframe_returns_overall_and_product_forecasts():
    report = forecast_sales_dataframe(_monthly_sales_df(), forecast_periods=3)

    assert report["history_months"] == 8
    assert len(report["overall_forecast"]) == 3
    assert report["summary"]["expected_products_sold"] > 0
    assert report["product_forecasts"][0]["product"] == "Spark"
    assert report["product_forecasts"][0]["expected_sold"] > 0
    assert report["product_forecasts"][0]["suggested_action"]
    assert "what_this_means" in report
    assert "stock_advice" in report
    assert "products_sold" in report["charts"]
    assert "product_units" in report["charts"]


def test_forecast_defaults_to_one_month_period():
    report = forecast_sales_dataframe(_monthly_sales_df())

    assert report["forecast_periods"] == 1
    assert len(report["overall_forecast"]) == 1


def test_forecast_requires_minimum_history():
    short_df = _monthly_sales_df(months=MIN_HISTORY_MONTHS - 1)

    with pytest.raises(ForecastError, match="at least"):
        forecast_sales_dataframe(short_df)


def test_generate_forecast_insight_mentions_products_and_numbers():
    report = forecast_sales_dataframe(_monthly_sales_df(), forecast_periods=3)
    insight = generate_forecast_insight(
        report["overall_forecast"],
        report["product_forecasts"],
        has_money=True,
        forecast_periods=3,
    )

    combined = " ".join(insight)
    assert "Spark" in combined
    assert "products sold" in combined


def test_forecast_sales_file_reads_csv(tmp_path: Path):
    csv_path = tmp_path / "sales_cleaned.csv"
    _monthly_sales_df().to_csv(csv_path, index=False)

    report = forecast_sales_file(csv_path)

    assert report["success"] is True
    assert report["source_file"] == "sales_cleaned.csv"


def test_forecast_sales_file_missing_path(tmp_path: Path):
    report = forecast_sales_file(tmp_path / "missing.csv")

    assert report["success"] is False
    assert "not found" in report["error"].lower()
