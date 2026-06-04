import pandas as pd
import pytest

from logic.forecast_methods import (
    BACKEND_EXPONENTIAL_SMOOTHING,
    BACKEND_LINEAR_REGRESSION,
    BACKEND_MOVING_AVERAGE,
    BACKEND_RANDOM_FOREST,
    BACKEND_SMART_FORECAST,
    COMPARABLE_BACKEND_METHODS,
    MIN_MONTHS_FOR_COMPARISON,
    FORECAST_METHOD_REGISTRY,
    METHOD_RECENT_SALES_FORECAST,
    METHOD_SMART_FORECAST,
    METHOD_TREND_FORECAST,
    _fit_exponential_smoothing_forecast,
    _fit_moving_average_forecast,
    _fit_random_forest_forecast,
    forecast_exponential_smoothing,
    forecast_linear_regression,
    forecast_moving_average,
    forecast_random_forest,
    normalize_forecast_method,
    predict_quantity_series,
    resolve_backend_method,
    run_forecast,
)


def _monthly_series(months: int = 8) -> pd.DataFrame:
    rows = []
    for month in range(1, months + 1):
        rows.append(
            {
                "period": pd.Period(f"2025-{month:02d}", freq="M"),
                "quantity": 20 + month,
                "money_made": (20 + month) * 50000,
                "profit": (20 + month) * 10000,
            }
        )
    return pd.DataFrame(rows)


def test_normalize_forecast_method_defaults_to_smart():
    assert normalize_forecast_method(None) == METHOD_SMART_FORECAST
    assert normalize_forecast_method("linear_regression") == METHOD_TREND_FORECAST
    assert normalize_forecast_method("moving_average") == METHOD_RECENT_SALES_FORECAST


def test_resolve_backend_method_mapping():
    assert resolve_backend_method(METHOD_TREND_FORECAST) == BACKEND_LINEAR_REGRESSION
    assert resolve_backend_method(METHOD_RECENT_SALES_FORECAST) == BACKEND_MOVING_AVERAGE
    assert resolve_backend_method(METHOD_SMART_FORECAST) == BACKEND_SMART_FORECAST


def test_forecast_linear_regression_standard_shape():
    result = forecast_linear_regression(_monthly_series(), forecast_months=3)

    assert result["method_key"] == BACKEND_LINEAR_REGRESSION
    assert result["display_name"] == "Trend Forecast"
    assert len(result["forecast"]) == 3
    assert result["forecast"][0]["month"]
    assert result["forecast"][0]["forecast_units"] > 0
    assert result["forecast"][0]["expected_revenue"] is not None
    assert result["confidence"] in {"High", "Medium", "Low"}
    assert result["explanation"]


def test_forecast_moving_average_standard_shape():
    result = forecast_moving_average(_monthly_series(), forecast_months=2)

    assert result["method_key"] == BACKEND_MOVING_AVERAGE
    assert result["display_name"] == "Recent Sales Forecast"
    assert len(result["forecast"]) == 2


def test_run_forecast_smart_selects_best_method_with_comparison():
    monthly = _monthly_series(MIN_MONTHS_FOR_COMPARISON)
    result = run_forecast(monthly, "Spark", 3, METHOD_SMART_FORECAST)

    assert result["method_key"] == BACKEND_SMART_FORECAST
    assert result["display_name"] == "Smart Forecast"
    assert result["resolved_method_key"] in COMPARABLE_BACKEND_METHODS
    assert result["method_comparison"] is not None
    assert result["chosen_method_display_name"] == result["method_comparison"]["winner_display_name"]
    assert "chose" in result["explanation"].lower()
    assert result["selected_product"] == "Spark"


def test_run_forecast_smart_falls_back_when_history_is_short():
    result = run_forecast(_monthly_series(4), None, 3, METHOD_SMART_FORECAST)

    assert result["resolved_method_key"] == BACKEND_LINEAR_REGRESSION
    assert result["method_comparison"] is None
    assert "not yet enough history" in result["explanation"].lower()


def test_run_forecast_recent_sales_differs_from_trend():
    monthly = _monthly_series()
    trend = run_forecast(monthly, None, 3, METHOD_TREND_FORECAST)
    recent = run_forecast(monthly, None, 3, METHOD_RECENT_SALES_FORECAST)

    assert trend["resolved_method_key"] == BACKEND_LINEAR_REGRESSION
    assert recent["resolved_method_key"] == BACKEND_MOVING_AVERAGE
    assert trend["forecast"][0]["forecast_units"] != recent["forecast"][0]["forecast_units"]


def test_registry_predict_matches_direct_wrappers():
    values = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0]
    assert predict_quantity_series(values, 2, BACKEND_LINEAR_REGRESSION) == pytest.approx(
        FORECAST_METHOD_REGISTRY[BACKEND_LINEAR_REGRESSION]["predict"](values, 2),
        rel=1e-9,
    )
    assert predict_quantity_series(values, 2, BACKEND_MOVING_AVERAGE) == pytest.approx(
        FORECAST_METHOD_REGISTRY[BACKEND_MOVING_AVERAGE]["predict"](values, 2),
        rel=1e-9,
    )
    assert predict_quantity_series(values, 2, BACKEND_EXPONENTIAL_SMOOTHING) == pytest.approx(
        FORECAST_METHOD_REGISTRY[BACKEND_EXPONENTIAL_SMOOTHING]["predict"](values, 2),
        rel=1e-9,
    )
    assert predict_quantity_series(values, 2, BACKEND_RANDOM_FOREST) == pytest.approx(
        FORECAST_METHOD_REGISTRY[BACKEND_RANDOM_FOREST]["predict"](values, 2),
        rel=1e-9,
    )


def test_comparable_methods_lists_all_four_backends():
    assert COMPARABLE_BACKEND_METHODS == [
        BACKEND_LINEAR_REGRESSION,
        BACKEND_MOVING_AVERAGE,
        BACKEND_EXPONENTIAL_SMOOTHING,
        BACKEND_RANDOM_FOREST,
    ]


def test_forecast_exponential_smoothing_standard_shape():
    result = forecast_exponential_smoothing(_monthly_series(), forecast_months=3)

    assert result["method_key"] == BACKEND_EXPONENTIAL_SMOOTHING
    assert result["display_name"] == "Smooth Trend Forecast"
    assert len(result["forecast"]) == 3
    assert result["forecast"][0]["forecast_units"] > 0
    assert result["explanation"]


def test_exponential_smoothing_flat_history_produces_flat_forecast():
    values = [50.0] * 6
    predictions = _fit_exponential_smoothing_forecast(values, periods=3)
    assert predictions == pytest.approx([50.0, 50.0, 50.0])


def test_moving_average_forecast_uses_recent_months():
    values = [10.0, 12.0, 14.0, 16.0, 18.0]
    predictions = _fit_moving_average_forecast(values, periods=2, window=3)
    assert predictions[0] == pytest.approx((14 + 16 + 18) / 3)


def test_forecast_random_forest_standard_shape():
    result = forecast_random_forest(_monthly_series(), forecast_months=3)

    assert result["method_key"] == BACKEND_RANDOM_FOREST
    assert result["display_name"] == "Pattern Forecast"
    assert len(result["forecast"]) == 3


def test_random_forest_produces_non_negative_predictions():
    values = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
    predictions = _fit_random_forest_forecast(values, periods=2)
    assert len(predictions) == 2
    assert all(value >= 0 for value in predictions)
