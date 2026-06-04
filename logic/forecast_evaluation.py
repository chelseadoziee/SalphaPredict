"""Holdout evaluation and accuracy metrics for forecast methods."""

from __future__ import annotations

import pandas as pd

from logic.forecast_methods import (
    BACKEND_LINEAR_REGRESSION,
    BACKEND_MOVING_AVERAGE,
    COMPARABLE_BACKEND_METHODS,
    FORECAST_METHOD_REGISTRY,
    HOLDOUT_MONTHS,
    MIN_HISTORY_MONTHS,
    MIN_MONTHS_FOR_COMPARISON,
    ForecastError,
    forecast_method_label,
    predict_quantity_series,
)


def compute_mae(actual: list[float], predicted: list[float]) -> float:
    if len(actual) != len(predicted) or not actual:
        return 0.0
    errors = [abs(float(a) - float(p)) for a, p in zip(actual, predicted)]
    return sum(errors) / len(errors)


def compute_rmse(actual: list[float], predicted: list[float]) -> float:
    if len(actual) != len(predicted) or not actual:
        return 0.0
    squared = [(float(a) - float(p)) ** 2 for a, p in zip(actual, predicted)]
    return (sum(squared) / len(squared)) ** 0.5


def compute_mape(actual: list[float], predicted: list[float]) -> float | None:
    """
    Mean absolute percentage error on non-zero actuals only.
    Returns None if every actual value is zero.
    """
    if len(actual) != len(predicted) or not actual:
        return None

    pct_errors: list[float] = []
    for act, pred in zip(actual, predicted):
        act_f = float(act)
        if act_f == 0:
            continue
        pct_errors.append(abs(act_f - float(pred)) / abs(act_f) * 100)

    if not pct_errors:
        return None
    return sum(pct_errors) / len(pct_errors)


def train_test_split_monthly(
    monthly_product_data: pd.DataFrame,
    holdout_months: int = HOLDOUT_MONTHS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split monthly rows into train (older) and test (most recent) periods."""
    if holdout_months < 1:
        raise ForecastError("Holdout months must be at least 1.")

    working = monthly_product_data.sort_values("period").reset_index(drop=True)
    if len(working) <= holdout_months:
        raise ForecastError(
            f"Need more than {holdout_months} months of data to hold out {holdout_months} for testing."
        )

    train_df = working.iloc[:-holdout_months].copy()
    test_df = working.iloc[-holdout_months:].copy()
    return train_df, test_df


def evaluate_method_on_holdout(
    backend_method: str,
    train_values: list[float],
    test_values: list[float],
) -> dict:
    """
    Fit on train_values only, predict len(test_values) steps, score against test_values.
    """
    if backend_method not in FORECAST_METHOD_REGISTRY:
        raise ForecastError(f"Unknown forecast method: {backend_method}")

    entry = FORECAST_METHOD_REGISTRY[backend_method]
    min_train = entry.get("min_train_months", MIN_HISTORY_MONTHS)
    if len(train_values) < min_train:
        raise ForecastError(
            f"{entry['display_name']} needs at least {min_train} training months; "
            f"only {len(train_values)} available."
        )

    horizon = len(test_values)
    predictions = predict_quantity_series(train_values, horizon, backend_method)
    actual = [float(value) for value in test_values]

    mape = compute_mape(actual, predictions)
    return {
        "method_key": backend_method,
        "display_name": entry["display_name"],
        "mae": round(compute_mae(actual, predictions), 4),
        "rmse": round(compute_rmse(actual, predictions), 4),
        "mape": round(mape, 4) if mape is not None else None,
        "predictions": predictions,
        "actual": actual,
        "train_months": len(train_values),
        "test_months": horizon,
    }


def _ranking_key(result: dict) -> tuple:
    """Lower is better: MAPE primary, then RMSE, then MAE."""
    mape = result.get("mape")
    if mape is None:
        mape_rank = float("inf")
    else:
        mape_rank = float(mape)
    return (mape_rank, float(result["rmse"]), float(result["mae"]))


def compare_methods(
    monthly_product_data: pd.DataFrame,
    holdout_months: int = HOLDOUT_MONTHS,
    methods: list[str] | None = None,
) -> dict:
    """
    Compare registered forecast methods using a train/test split on monthly quantity.

    Returns ranked results, winner, and split metadata for Smart Forecast (later phases).
    """
    methods = methods or list(COMPARABLE_BACKEND_METHODS)
    if len(monthly_product_data) < MIN_MONTHS_FOR_COMPARISON:
        raise ForecastError(
            f"Need at least {MIN_MONTHS_FOR_COMPARISON} months of history to compare methods "
            f"({MIN_HISTORY_MONTHS} train + {holdout_months} test). "
            f"This series only has {len(monthly_product_data)} month(s)."
        )

    train_df, test_df = train_test_split_monthly(monthly_product_data, holdout_months)
    train_values = [float(value) for value in train_df["quantity"].tolist()]
    test_values = [float(value) for value in test_df["quantity"].tolist()]

    results: list[dict] = []
    errors: list[dict] = []

    for backend_method in methods:
        if backend_method not in FORECAST_METHOD_REGISTRY:
            continue
        try:
            results.append(
                evaluate_method_on_holdout(backend_method, train_values, test_values)
            )
        except ForecastError as exc:
            errors.append(
                {
                    "method_key": backend_method,
                    "display_name": forecast_method_label(backend_method),
                    "error": str(exc),
                }
            )

    if not results:
        raise ForecastError(
            "No forecast methods could be evaluated. "
            + (errors[0]["error"] if errors else "Check sales history length.")
        )

    ranked = sorted(results, key=_ranking_key)
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index

    winner = ranked[0]
    return {
        "holdout_months": holdout_months,
        "train_months": len(train_df),
        "test_months": len(test_df),
        "train_period_start": str(train_df["period"].iloc[0]),
        "train_period_end": str(train_df["period"].iloc[-1]),
        "test_period_start": str(test_df["period"].iloc[0]),
        "test_period_end": str(test_df["period"].iloc[-1]),
        "results": ranked,
        "winner": winner,
        "winner_method_key": winner["method_key"],
        "winner_display_name": winner["display_name"],
        "errors": errors,
    }


def select_best_method(
    monthly_product_data: pd.DataFrame,
    holdout_months: int = HOLDOUT_MONTHS,
    methods: list[str] | None = None,
) -> str:
    """Return backend method key with best holdout MAPE (ties broken by RMSE, then MAE)."""
    comparison = compare_methods(monthly_product_data, holdout_months, methods)
    return comparison["winner_method_key"]


def format_method_comparison_for_ui(comparison: dict | None) -> dict | None:
    """Shape holdout comparison results for dashboard tables."""
    if not comparison:
        return None

    rows: list[dict] = []
    winner_key = comparison["winner_method_key"]
    for result in comparison["results"]:
        rows.append(
            {
                "method_key": result["method_key"],
                "display_name": result["display_name"],
                "rank": result["rank"],
                "mae": result["mae"],
                "rmse": result["rmse"],
                "mape": result["mape"],
                "is_winner": result["method_key"] == winner_key,
            }
        )

    return {
        "holdout_months": comparison["holdout_months"],
        "train_months": comparison["train_months"],
        "test_months": comparison["test_months"],
        "train_period_start": comparison["train_period_start"],
        "train_period_end": comparison["train_period_end"],
        "test_period_start": comparison["test_period_start"],
        "test_period_end": comparison["test_period_end"],
        "winner_method_key": winner_key,
        "winner_display_name": comparison["winner_display_name"],
        "chosen_display_name": comparison["winner_display_name"],
        "rows": rows,
    }
