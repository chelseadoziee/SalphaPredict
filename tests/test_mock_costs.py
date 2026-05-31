import pandas as pd
import pytest

from logic.mock_costs import (
    MOCK_UNIT_COSTS,
    MockCostError,
    apply_profit_columns,
    build_mock_excel_dataframe,
    calculate_profit_row,
    get_mock_unit_cost,
)


def test_calculate_profit_row_spark():
    result = calculate_profit_row(
        quantity=4,
        unit_price=80_000,
        unit_cost=MOCK_UNIT_COSTS["Spark"],
    )

    assert result["Total Sales"] == 320_000
    assert result["Total Cost"] == 192_000
    assert result["Profit"] == 128_000
    assert result["Profit Margin"] == 40.0


def test_calculate_profit_row_powerflo_200():
    result = calculate_profit_row(
        quantity=2,
        unit_price=2_600_000,
        unit_cost=MOCK_UNIT_COSTS["POWERFLO 200"],
    )

    assert result["Total Sales"] == 5_200_000
    assert result["Total Cost"] == 3_900_000
    assert result["Profit"] == 1_300_000
    assert pytest.approx(result["Profit Margin"], rel=1e-6) == 25.0


def test_get_mock_unit_cost_unknown_product():
    with pytest.raises(MockCostError, match="No mock unit cost"):
        get_mock_unit_cost("Unknown Panel")


def test_apply_profit_columns_calculates_loss_when_cost_exceeds_sales():
    cleaned = pd.DataFrame(
        {
            "sale_date": ["2025-01-08"],
            "product": ["Spark"],
            "quantity": [2],
            "unit_price": [40_000],
            "total_amount": [80_000],
            "unit_cost": [50_000],
        }
    )

    result, report = apply_profit_columns(cleaned)

    assert result.loc[0, "profit"] == -20_000
    assert result.loc[0, "loss"] == 20_000
    assert report["rows_with_loss"] == 1


def test_apply_profit_columns_calculates_missing_values():
    cleaned = pd.DataFrame(
        {
            "sale_date": ["2025-01-08"],
            "product": ["Spark"],
            "quantity": [4],
            "unit_price": [80_000],
            "total_amount": [320_000],
        }
    )

    result, report = apply_profit_columns(cleaned)

    assert report["used_mock_unit_costs"] is True
    assert result.loc[0, "unit_cost"] == 48_000
    assert result.loc[0, "total_cost"] == 192_000
    assert result.loc[0, "profit"] == 128_000
    assert result.loc[0, "profit_margin"] == 40.0


def test_apply_profit_columns_keeps_uploaded_profit_values():
    cleaned = pd.DataFrame(
        {
            "sale_date": ["2025-01-08"],
            "product": ["Spark"],
            "quantity": [4],
            "unit_price": [80_000],
            "total_amount": [320_000],
            "unit_cost": [50_000],
            "total_cost": [200_000],
            "profit": [120_000],
            "profit_margin": [37.5],
        }
    )

    result, report = apply_profit_columns(cleaned)

    assert report["used_mock_unit_costs"] is False
    assert result.loc[0, "profit"] == 120_000
    assert result.loc[0, "profit_margin"] == 37.5


def test_build_mock_excel_dataframe_from_cleaned_rows():
    cleaned = pd.DataFrame(
        {
            "sale_date": ["2025-01-08"],
            "product": ["Spark"],
            "quantity": [4],
            "unit_price": [80_000],
            "total_amount": [320_000],
        }
    )

    excel_df = build_mock_excel_dataframe(cleaned)

    assert list(excel_df.columns) == [
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
    ]
    assert excel_df.loc[0, "Unit Cost"] == 48_000
    assert excel_df.loc[0, "Profit"] == 128_000
    assert excel_df.loc[0, "Category"] == "Inverter"
