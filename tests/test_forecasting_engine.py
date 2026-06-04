from pathlib import Path

import pandas as pd
import pytest

from logic.forecast_methods import (
    DEFAULT_FORECAST_METHOD,
    METHOD_RECENT_SALES_FORECAST,
    METHOD_SMART_FORECAST,
    METHOD_TREND_FORECAST,
)
from logic.forecasting_engine import (
    ForecastError,
    MIN_HISTORY_MONTHS,
    forecast_sales_dataframe,
    forecast_sales_file,
    generate_forecast_insight,
    list_forecast_products,
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
    assert "standard_forecast" in report
    assert report["standard_forecast"]["display_name"]
    assert "products_sold" in report["charts"]
    assert "product_units" in report["charts"]


def test_forecast_defaults_to_smart_forecast_method():
    report = forecast_sales_dataframe(_monthly_sales_df())

    assert report["forecast_periods"] == 1
    assert report["forecast_method"] == METHOD_SMART_FORECAST
    assert report["forecast_model_label"] == "Smart Forecast"
    assert report["standard_forecast"]["method_key"] == "smart_forecast"
    assert "forecast_method_options" not in report["controls"]


def test_forecast_smart_includes_method_comparison_table():
    report = forecast_sales_dataframe(_monthly_sales_df(), forecast_periods=3)

    assert report.get("is_smart_forecast") is True
    assert report.get("forecast_explanation")
    assert len(report.get("smart_forecast_methods_tested", [])) == 4

    comparison = report.get("method_comparison")
    assert comparison is not None
    assert len(comparison["rows"]) == 4
    assert comparison["chosen_display_name"]
    assert report["chosen_method_display_name"] == comparison["chosen_display_name"]
    assert report["resolved_method_key"] == comparison["winner_method_key"]


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


def test_forecast_product_filter_focuses_on_one_product():
    report = forecast_sales_dataframe(
        _monthly_sales_df(), forecast_periods=3, product="JET PRO"
    )

    assert report["selected_product"] == "JET PRO"
    assert report["view_mode"] == "product_journey"
    assert len(report["product_forecasts"]) == 1
    assert "journey_line" in report["charts"]
    assert "products_sold" not in report["charts"]


def test_forecast_recent_sales_method_still_supported_for_api():
    report = forecast_sales_dataframe(
        _monthly_sales_df(), forecast_periods=3, method=METHOD_RECENT_SALES_FORECAST
    )

    assert report["forecast_method"] == METHOD_RECENT_SALES_FORECAST
    assert report["standard_forecast"]["resolved_method_key"] == "moving_average"


def test_forecast_trend_method_still_supported_for_api():
    report = forecast_sales_dataframe(
        _monthly_sales_df(), forecast_periods=3, method=METHOD_TREND_FORECAST
    )

    assert report["forecast_method"] == METHOD_TREND_FORECAST
    assert report["standard_forecast"]["resolved_method_key"] == "linear_regression"


def test_generate_forecast_insight_mentions_smart_choice():
    report = forecast_sales_dataframe(_monthly_sales_df(), forecast_periods=3)
    insight = generate_forecast_insight(
        report["overall_forecast"],
        report["product_forecasts"],
        has_money=True,
        forecast_periods=3,
        forecast_method=METHOD_SMART_FORECAST,
        chosen_method_display_name=report["chosen_method_display_name"],
    )

    assert "Smart Forecast" in insight[0]
    assert report["chosen_method_display_name"] in insight[0]


def test_forecast_invalid_method_falls_back_to_smart():
    report = forecast_sales_dataframe(_monthly_sales_df(), method="unknown-model")

    assert report["forecast_method"] == DEFAULT_FORECAST_METHOD


def test_list_forecast_products_reads_csv(tmp_path: Path):
    csv_path = tmp_path / "sales_cleaned.csv"
    _monthly_sales_df().to_csv(csv_path, index=False)

    result = list_forecast_products(csv_path)

    assert result["success"] is True
    assert "Spark" in result["products"]
