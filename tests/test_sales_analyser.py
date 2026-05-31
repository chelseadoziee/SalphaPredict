from pathlib import Path

import pandas as pd
import pytest

from logic.sales_analyser import (
    SalesAnalysisError,
    analyse_sales_dataframe,
    analyse_sales_file,
    generate_key_insight,
    get_high_value_low_volume_products,
    get_product_overview,
    get_revenue_by_product,
    get_top_products_by_quantity,
)


def _sample_sales_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sale_date": pd.to_datetime(
                [
                    "2024-01-05",
                    "2024-01-20",
                    "2024-02-03",
                    "2024-02-18",
                    "2024-03-01",
                    "2024-03-12",
                ]
            ),
            "product": [
                "Solar Panel",
                "Solar Panel",
                "Inverter",
                "Battery",
                "Cable Kit",
                "Solar Panel",
            ],
            "quantity": [20, 15, 8, 5, 2, 10],
            "total_amount": [5000, 3750, 9600, 4000, 90, 2500],
            "region": ["Lagos", "Lagos", "Abuja", "Lagos", "Port Harcourt", "Abuja"],
        }
    )


def _premium_pattern_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sale_date": pd.to_datetime(["2024-01-01"] * 4),
            "product": ["Spark", "JET PRO", "POWERFLO 200", "Basic Cable"],
            "quantity": [120, 95, 12, 8],
            "total_amount": [24000, 28500, 48000, 400],
        }
    )


def _mock_insight_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sale_date": pd.to_datetime(["2024-01-01"] * 5),
            "product": ["Spark", "JET PRO", "POWERFLO 200", "POWERFLO 100", "Basic Cable"],
            "quantity": [268, 262, 19, 15, 10],
            "total_amount": [5360000, 5240000, 23400000, 12000000, 50000],
        }
    )


def test_analyse_sales_dataframe_summary_and_rankings():
    report = analyse_sales_dataframe(_sample_sales_df())

    assert report["summary"]["total_units"] == 60
    assert report["summary"]["total_revenue"] == 24940.0
    assert report["summary"]["unique_products"] == 4
    assert report["top_products"][0]["product"] == "Solar Panel"
    assert report["top_products"][0]["quantity"] == 45
    assert report["product_overview"][0]["product"] == "Solar Panel"
    assert report["product_overview"][0]["quantity"] == 45
    assert report["revenue_by_product"][0]["product"] == "Inverter"
    assert len(report["monthly_trend"]) == 3
    assert report["demand_trend"]["direction"] in {"up", "down", "stable", "insufficient_data"}
    assert report["region_breakdown"][0]["region"] == "Lagos"
    assert len(report["key_insight"]) >= 2
    assert "revenue_by_product" in report["charts"]


def test_product_overview_includes_quantity_and_money_fields():
    overview = get_product_overview(_sample_sales_df())

    assert len(overview) == 4
    assert overview[0]["quantity_share_pct"] is not None
    assert overview[0]["revenue"] is not None
    assert overview[0]["revenue_share_pct"] is not None


def test_high_value_low_volume_identifies_premium_products():
    working = _premium_pattern_df()
    premium = get_high_value_low_volume_products(working)

    assert any(row["product"] == "POWERFLO 200" for row in premium)
    assert all(row["product"] != "Spark" for row in premium)


def test_revenue_by_product_orders_by_revenue():
    revenue_rows = get_revenue_by_product(_premium_pattern_df())

    assert revenue_rows[0]["product"] == "POWERFLO 200"
    assert revenue_rows[0]["revenue"] == 48000.0


def test_generate_key_insight_mentions_real_products_and_values():
    working = _mock_insight_df()
    insight = generate_key_insight(
        get_top_products_by_quantity(working),
        get_revenue_by_product(working),
        get_high_value_low_volume_products(working),
    )

    combined = " ".join(insight)
    assert "Spark" in combined
    assert "268 units" in combined
    assert "JET PRO" in combined
    assert "POWERFLO 200" in combined
    assert "19 units" in combined
    assert "₦23,400,000.00" in combined
    assert "regular restocking" in combined
    assert "careful tracking" in combined


def test_generate_key_insight_for_small_dataset():
    working = _premium_pattern_df()
    insight = generate_key_insight(
        get_top_products_by_quantity(working),
        get_revenue_by_product(working),
        get_high_value_low_volume_products(working),
    )

    assert insight[0].startswith("Spark")
    assert "POWERFLO 200" in " ".join(insight)


def test_analyse_sales_dataframe_requires_core_columns():
    with pytest.raises(SalesAnalysisError, match="missing required column"):
        analyse_sales_dataframe(pd.DataFrame({"product": ["A"], "quantity": [1]}))


def test_analyse_sales_file_reads_csv(tmp_path: Path):
    csv_path = tmp_path / "sales_cleaned.csv"
    _sample_sales_df().to_csv(csv_path, index=False)

    report = analyse_sales_file(csv_path)

    assert report["success"] is True
    assert report["source_file"] == "sales_cleaned.csv"
    assert report["summary"]["transaction_count"] == 6


def test_analyse_sales_file_missing_path(tmp_path: Path):
    report = analyse_sales_file(tmp_path / "missing.csv")

    assert report["success"] is False
    assert "not found" in report["error"].lower()
