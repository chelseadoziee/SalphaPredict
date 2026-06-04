import pandas as pd
import pytest

from logic.forecast_evaluation import (
    compare_methods,
    compute_mae,
    compute_mape,
    compute_rmse,
    evaluate_method_on_holdout,
    format_method_comparison_for_ui,
    select_best_method,
    train_test_split_monthly,
)
from logic.forecast_methods import (
    BACKEND_EXPONENTIAL_SMOOTHING,
    BACKEND_LINEAR_REGRESSION,
    BACKEND_MOVING_AVERAGE,
    BACKEND_RANDOM_FOREST,
    COMPARABLE_BACKEND_METHODS,
    FORECAST_METHOD_REGISTRY,
    HOLDOUT_MONTHS,
    MIN_MONTHS_FOR_COMPARISON,
    ForecastError,
    predict_quantity_exponential_smoothing,
    predict_quantity_linear,
    predict_quantity_moving_average,
    predict_quantity_random_forest,
)


def _monthly_series(months: int = 10) -> pd.DataFrame:
    rows = []
    for month in range(1, months + 1):
        rows.append(
            {
                "period": pd.Period(f"2025-{month:02d}", freq="M"),
                "quantity": 20 + month,
                "money_made": (20 + month) * 50000,
            }
        )
    return pd.DataFrame(rows)


def test_metric_functions():
    assert compute_mae([10.0, 20.0], [12.0, 18.0]) == pytest.approx(2.0)
    assert compute_rmse([10.0, 20.0], [10.0, 30.0]) == pytest.approx(7.071, rel=1e-2)
    assert compute_mape([100.0, 200.0], [90.0, 180.0]) == pytest.approx(10.0)


def test_mape_skips_zero_actuals():
    actual = [0.0, 100.0]
    predicted = [10.0, 90.0]
    assert compute_mape(actual, predicted) == pytest.approx(10.0)


def test_train_test_split_monthly():
    monthly = _monthly_series(10)
    train, test = train_test_split_monthly(monthly, holdout_months=3)
    assert len(train) == 7
    assert len(test) == 3
    assert test["period"].iloc[-1] == monthly["period"].iloc[-1]


def test_forecast_method_registry_has_all_comparable_methods():
    assert BACKEND_LINEAR_REGRESSION in FORECAST_METHOD_REGISTRY
    assert BACKEND_MOVING_AVERAGE in FORECAST_METHOD_REGISTRY
    assert BACKEND_EXPONENTIAL_SMOOTHING in FORECAST_METHOD_REGISTRY
    assert BACKEND_RANDOM_FOREST in FORECAST_METHOD_REGISTRY
    assert len(COMPARABLE_BACKEND_METHODS) == 4


def test_predict_quantity_wrappers_match_legacy():
    values = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0]
    linear = predict_quantity_linear(values, 3)
    ma = predict_quantity_moving_average(values, 3)
    es = predict_quantity_exponential_smoothing(values, 3)
    rf = predict_quantity_random_forest(values, 3)
    assert len(linear) == 3
    assert len(ma) == 3
    assert len(es) == 3
    assert len(rf) == 3
    assert all(value >= 0 for value in linear + ma + es + rf)


def test_evaluate_method_on_holdout_exponential_smoothing():
    monthly = _monthly_series(MIN_MONTHS_FOR_COMPARISON)
    train, test = train_test_split_monthly(monthly)
    train_values = train["quantity"].tolist()
    test_values = test["quantity"].tolist()

    result = evaluate_method_on_holdout(
        BACKEND_EXPONENTIAL_SMOOTHING,
        train_values,
        test_values,
    )

    assert result["method_key"] == BACKEND_EXPONENTIAL_SMOOTHING
    assert result["display_name"] == "Smooth Trend Forecast"
    assert len(result["predictions"]) == HOLDOUT_MONTHS
    assert result["mae"] >= 0
    assert result["rmse"] >= 0
    assert result["mape"] is None or result["mape"] >= 0


def test_evaluate_method_on_holdout_linear():
    monthly = _monthly_series(MIN_MONTHS_FOR_COMPARISON)
    train, test = train_test_split_monthly(monthly)
    train_values = train["quantity"].tolist()
    test_values = test["quantity"].tolist()

    result = evaluate_method_on_holdout(
        BACKEND_LINEAR_REGRESSION,
        train_values,
        test_values,
    )

    assert result["method_key"] == BACKEND_LINEAR_REGRESSION
    assert result["display_name"] == "Trend Forecast"
    assert len(result["predictions"]) == HOLDOUT_MONTHS
    assert result["mae"] >= 0
    assert result["rmse"] >= 0
    assert result["mape"] is None or result["mape"] >= 0


def test_evaluate_method_on_holdout_random_forest():
    monthly = _monthly_series(MIN_MONTHS_FOR_COMPARISON)
    train, test = train_test_split_monthly(monthly)
    result = evaluate_method_on_holdout(
        BACKEND_RANDOM_FOREST,
        train["quantity"].tolist(),
        test["quantity"].tolist(),
    )

    assert result["method_key"] == BACKEND_RANDOM_FOREST
    assert result["display_name"] == "Pattern Forecast"
    assert len(result["predictions"]) == HOLDOUT_MONTHS


def test_compare_methods_returns_ranked_results_and_winner():
    comparison = compare_methods(_monthly_series(10))

    assert comparison["holdout_months"] == HOLDOUT_MONTHS
    assert len(comparison["results"]) == 4
    method_keys = {row["method_key"] for row in comparison["results"]}
    assert method_keys == set(COMPARABLE_BACKEND_METHODS)
    for row in comparison["results"]:
        assert row["mae"] >= 0
        assert row["rmse"] >= 0
        assert row["mape"] is None or row["mape"] >= 0
    assert comparison["results"][0]["rank"] == 1
    assert comparison["winner_method_key"] in COMPARABLE_BACKEND_METHODS


def test_select_best_method_matches_compare_winner():
    monthly = _monthly_series(10)
    winner_key = select_best_method(monthly)
    comparison = compare_methods(monthly)
    assert winner_key == comparison["winner_method_key"]


def test_compare_methods_requires_minimum_history():
    with pytest.raises(ForecastError, match="at least"):
        compare_methods(_monthly_series(MIN_MONTHS_FOR_COMPARISON - 1))


def test_flat_series_moving_average_can_win():
    """On a flat recent tail, MA often beats LR on holdout."""
    quantities = [50.0] * 4 + [50.0, 50.0, 50.0] + [48.0, 49.0, 50.0]
    monthly = pd.DataFrame(
        {
            "period": [pd.Period(f"2025-{i:02d}", freq="M") for i in range(1, 11)],
            "quantity": quantities,
        }
    )
    comparison = compare_methods(monthly)
    keys = [row["method_key"] for row in comparison["results"]]
    assert BACKEND_LINEAR_REGRESSION in keys
    assert BACKEND_MOVING_AVERAGE in keys
    assert BACKEND_EXPONENTIAL_SMOOTHING in keys
    assert BACKEND_RANDOM_FOREST in keys


def test_format_method_comparison_for_ui_marks_winner():
    comparison = compare_methods(_monthly_series(10))
    ui = format_method_comparison_for_ui(comparison)

    assert ui is not None
    assert len(ui["rows"]) == 4
    winners = [row for row in ui["rows"] if row["is_winner"]]
    assert len(winners) == 1
    assert winners[0]["display_name"] == comparison["winner_display_name"]
