"""Shared multi-method forecasting for SalphaPredict."""

from __future__ import annotations

from typing import Callable, TypedDict

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

from logic.sales_analyser import _round_number

MIN_HISTORY_MONTHS = 4
MAX_FORECAST_MONTHS = 6
DEFAULT_MA_WINDOW = 3
DEFAULT_ES_ALPHA = 0.3
DEFAULT_RF_MAX_LAGS = 3
DEFAULT_RF_ESTIMATORS = 50
HOLDOUT_MONTHS = 3
MIN_MONTHS_FOR_COMPARISON = MIN_HISTORY_MONTHS + HOLDOUT_MONTHS

# UI method keys (dropdown values)
METHOD_SMART_FORECAST = "smart_forecast"
METHOD_TREND_FORECAST = "trend_forecast"
METHOD_RECENT_SALES_FORECAST = "recent_sales_forecast"
DEFAULT_FORECAST_METHOD = METHOD_SMART_FORECAST
ALLOWED_FORECAST_METHODS = (
    METHOD_SMART_FORECAST,
    METHOD_TREND_FORECAST,
    METHOD_RECENT_SALES_FORECAST,
)

# Backend / technical method keys (stored on forecast results)
BACKEND_LINEAR_REGRESSION = "linear_regression"
BACKEND_MOVING_AVERAGE = "moving_average"
BACKEND_EXPONENTIAL_SMOOTHING = "exponential_smoothing"
BACKEND_RANDOM_FOREST = "random_forest"
BACKEND_SMART_FORECAST = "smart_forecast"

METHOD_DISPLAY_NAMES: dict[str, str] = {
    METHOD_SMART_FORECAST: "Smart Forecast",
    METHOD_TREND_FORECAST: "Trend Forecast",
    METHOD_RECENT_SALES_FORECAST: "Recent Sales Forecast",
    BACKEND_LINEAR_REGRESSION: "Trend Forecast",
    BACKEND_MOVING_AVERAGE: "Recent Sales Forecast",
    BACKEND_EXPONENTIAL_SMOOTHING: "Smooth Trend Forecast",
    BACKEND_RANDOM_FOREST: "Pattern Forecast",
}

METHOD_EXPLANATIONS: dict[str, str] = {
    BACKEND_LINEAR_REGRESSION: "This forecast follows the overall sales direction.",
    BACKEND_MOVING_AVERAGE: "This forecast is based on recent monthly sales levels.",
    BACKEND_EXPONENTIAL_SMOOTHING: (
        "This forecast smooths recent sales and projects that level forward."
    ),
    BACKEND_RANDOM_FOREST: (
        "This forecast learns patterns from recent monthly sales history."
    ),
    BACKEND_SMART_FORECAST: (
        "Smart Forecast compares forecast methods on recent sales and uses the most accurate."
    ),
}

# Legacy aliases (older query params / tests)
FORECAST_MODEL_LINEAR = METHOD_TREND_FORECAST
FORECAST_MODEL_MOVING_AVERAGE = METHOD_RECENT_SALES_FORECAST
DEFAULT_FORECAST_MODEL = DEFAULT_FORECAST_METHOD
ALLOWED_FORECAST_MODELS = ALLOWED_FORECAST_METHODS

PredictQuantityFn = Callable[[list[float], int], list[float]]


class ForecastMethodEntry(TypedDict):
    predict: PredictQuantityFn
    display_name: str
    explanation: str
    min_train_months: int


class ForecastError(Exception):
    """Raised when cleaned sales data cannot be forecast."""


def _period_label(period: pd.Period) -> str:
    return str(period)


def _future_periods(last_period: pd.Period, count: int) -> list[str]:
    return [_period_label(last_period + offset) for offset in range(1, count + 1)]


def _confidence_label(history_months: int) -> str:
    if history_months >= 12:
        return "High"
    if history_months >= 8:
        return "Medium"
    return "Low"


def _fit_linear_forecast(values: list[float], periods: int) -> list[float]:
    if len(values) < MIN_HISTORY_MONTHS:
        raise ForecastError(
            f"Need at least {MIN_HISTORY_MONTHS} months of history to forecast."
        )

    x_values = np.arange(len(values)).reshape(-1, 1)
    y_values = np.array(values, dtype=float)
    model = LinearRegression()
    model.fit(x_values, y_values)

    future_x = np.arange(len(values), len(values) + periods).reshape(-1, 1)
    predictions = model.predict(future_x)
    return [float(max(0, value)) for value in predictions]


def _moving_average_window(history_length: int) -> int:
    return max(2, min(DEFAULT_MA_WINDOW, history_length))


def _fit_moving_average_forecast(
    values: list[float],
    periods: int,
    window: int | None = None,
) -> list[float]:
    if len(values) < MIN_HISTORY_MONTHS:
        raise ForecastError(
            f"Need at least {MIN_HISTORY_MONTHS} months of history to forecast."
        )

    ma_window = window or _moving_average_window(len(values))
    ma_window = max(2, min(ma_window, len(values)))

    extended = [float(value) for value in values]
    predictions: list[float] = []
    for _ in range(periods):
        recent = extended[-ma_window:]
        predicted = sum(recent) / len(recent)
        predicted = max(0.0, float(predicted))
        predictions.append(predicted)
        extended.append(predicted)

    return predictions


def _fit_exponential_smoothing_forecast(
    values: list[float],
    periods: int,
    alpha: float | None = None,
) -> list[float]:
    if len(values) < MIN_HISTORY_MONTHS:
        raise ForecastError(
            f"Need at least {MIN_HISTORY_MONTHS} months of history to forecast."
        )

    smoothing_alpha = DEFAULT_ES_ALPHA if alpha is None else float(alpha)
    smoothing_alpha = max(0.01, min(0.99, smoothing_alpha))

    level = float(values[0])
    for raw in values[1:]:
        observation = float(raw)
        level = smoothing_alpha * observation + (1 - smoothing_alpha) * level

    predictions: list[float] = []
    for _ in range(periods):
        pred = max(0.0, level)
        predictions.append(pred)
        level = smoothing_alpha * pred + (1 - smoothing_alpha) * level

    return predictions


def _random_forest_max_lags(history_length: int) -> int:
    return max(1, min(DEFAULT_RF_MAX_LAGS, history_length - 2))


def _fit_random_forest_forecast(values: list[float], periods: int) -> list[float]:
    if len(values) < MIN_HISTORY_MONTHS:
        raise ForecastError(
            f"Need at least {MIN_HISTORY_MONTHS} months of history to forecast."
        )

    series = [float(value) for value in values]
    max_lags = _random_forest_max_lags(len(series))
    features: list[list[float]] = []
    targets: list[float] = []
    for index in range(max_lags, len(series)):
        lag_values = [series[index - lag_offset - 1] for lag_offset in range(max_lags)]
        features.append(lag_values + [float(index)])
        targets.append(series[index])

    if len(features) < 2:
        return _fit_linear_forecast(values, periods)

    model = RandomForestRegressor(
        n_estimators=DEFAULT_RF_ESTIMATORS,
        max_depth=4,
        min_samples_leaf=2,
        random_state=42,
    )
    model.fit(np.array(features), np.array(targets))

    extended = series[:]
    predictions: list[float] = []
    for _ in range(periods):
        index = len(extended)
        lag_values = [extended[index - lag_offset - 1] for lag_offset in range(max_lags)]
        row = np.array([lag_values + [float(index)]])
        predicted = max(0.0, float(model.predict(row)[0]))
        predictions.append(predicted)
        extended.append(predicted)

    return predictions


def predict_quantity_linear(train_values: list[float], horizon: int) -> list[float]:
    """Predict future unit counts using linear regression (Trend Forecast)."""
    return _fit_linear_forecast(train_values, horizon)


def predict_quantity_moving_average(train_values: list[float], horizon: int) -> list[float]:
    """Predict future unit counts using a rolling moving average (Recent Sales Forecast)."""
    return _fit_moving_average_forecast(train_values, horizon)


def predict_quantity_exponential_smoothing(
    train_values: list[float],
    horizon: int,
) -> list[float]:
    """Predict future unit counts using simple exponential smoothing (Smooth Trend Forecast)."""
    return _fit_exponential_smoothing_forecast(train_values, horizon)


def predict_quantity_random_forest(train_values: list[float], horizon: int) -> list[float]:
    """Predict future unit counts using a random forest on lagged sales (Pattern Forecast)."""
    return _fit_random_forest_forecast(train_values, horizon)


FORECAST_METHOD_REGISTRY: dict[str, ForecastMethodEntry] = {
    BACKEND_LINEAR_REGRESSION: {
        "predict": predict_quantity_linear,
        "display_name": METHOD_DISPLAY_NAMES[BACKEND_LINEAR_REGRESSION],
        "explanation": METHOD_EXPLANATIONS[BACKEND_LINEAR_REGRESSION],
        "min_train_months": MIN_HISTORY_MONTHS,
    },
    BACKEND_MOVING_AVERAGE: {
        "predict": predict_quantity_moving_average,
        "display_name": METHOD_DISPLAY_NAMES[BACKEND_MOVING_AVERAGE],
        "explanation": METHOD_EXPLANATIONS[BACKEND_MOVING_AVERAGE],
        "min_train_months": MIN_HISTORY_MONTHS,
    },
    BACKEND_EXPONENTIAL_SMOOTHING: {
        "predict": predict_quantity_exponential_smoothing,
        "display_name": METHOD_DISPLAY_NAMES[BACKEND_EXPONENTIAL_SMOOTHING],
        "explanation": METHOD_EXPLANATIONS[BACKEND_EXPONENTIAL_SMOOTHING],
        "min_train_months": MIN_HISTORY_MONTHS,
    },
    BACKEND_RANDOM_FOREST: {
        "predict": predict_quantity_random_forest,
        "display_name": METHOD_DISPLAY_NAMES[BACKEND_RANDOM_FOREST],
        "explanation": METHOD_EXPLANATIONS[BACKEND_RANDOM_FOREST],
        "min_train_months": MIN_HISTORY_MONTHS,
    },
}

COMPARABLE_BACKEND_METHODS: list[str] = [
    BACKEND_LINEAR_REGRESSION,
    BACKEND_MOVING_AVERAGE,
    BACKEND_EXPONENTIAL_SMOOTHING,
    BACKEND_RANDOM_FOREST,
]


def predict_quantity_series(
    train_values: list[float],
    horizon: int,
    backend_method: str,
) -> list[float]:
    """Run a registered backend on training values and return horizon predictions."""
    if backend_method not in FORECAST_METHOD_REGISTRY:
        raise ForecastError(f"Unknown forecast method: {backend_method}")
    entry = FORECAST_METHOD_REGISTRY[backend_method]
    if len(train_values) < entry["min_train_months"]:
        raise ForecastError(
            f"Need at least {entry['min_train_months']} months of training data for "
            f"{entry['display_name']}."
        )
    return entry["predict"](train_values, horizon)


def normalize_forecast_method(method: str | None) -> str:
    """Normalize UI or legacy method keys to a supported forecast method."""
    if method is None:
        return DEFAULT_FORECAST_METHOD
    cleaned = str(method).strip().lower().replace(" ", "_")
    aliases = {
        "smart": METHOD_SMART_FORECAST,
        "smart-forecast": METHOD_SMART_FORECAST,
        "trend": METHOD_TREND_FORECAST,
        "trend-forecast": METHOD_TREND_FORECAST,
        "trend_forecast": METHOD_TREND_FORECAST,
        "recent_sales": METHOD_RECENT_SALES_FORECAST,
        "recent-sales": METHOD_RECENT_SALES_FORECAST,
        "recent_sales_forecast": METHOD_RECENT_SALES_FORECAST,
        "linear": METHOD_TREND_FORECAST,
        "linear_regression": METHOD_TREND_FORECAST,
        "lr": METHOD_TREND_FORECAST,
        "regression": METHOD_TREND_FORECAST,
        "moving_average": METHOD_RECENT_SALES_FORECAST,
        "moving-average": METHOD_RECENT_SALES_FORECAST,
        "ma": METHOD_RECENT_SALES_FORECAST,
        "moving_avg": METHOD_RECENT_SALES_FORECAST,
    }
    cleaned = aliases.get(cleaned, cleaned)
    if cleaned in ALLOWED_FORECAST_METHODS:
        return cleaned
    return DEFAULT_FORECAST_METHOD


def resolve_backend_method(method: str) -> str:
    """Map a UI method to the backend forecaster to execute."""
    if method == METHOD_RECENT_SALES_FORECAST:
        return BACKEND_MOVING_AVERAGE
    if method == METHOD_TREND_FORECAST:
        return BACKEND_LINEAR_REGRESSION
    if method == METHOD_SMART_FORECAST:
        return BACKEND_SMART_FORECAST
    return BACKEND_LINEAR_REGRESSION


def _smart_forecast_explanation(chosen_display_name: str) -> str:
    return (
        f"Smart Forecast chose {chosen_display_name} based on recent accuracy "
        f"on the last {HOLDOUT_MONTHS} months of sales (MAPE, then RMSE, then MAE)."
    )


def _smart_forecast_fallback_explanation() -> str:
    return (
        f"Smart Forecast used {METHOD_DISPLAY_NAMES[BACKEND_LINEAR_REGRESSION]} because "
        f"there is not yet enough history to compare methods "
        f"(need {MIN_MONTHS_FOR_COMPARISON} months)."
    )


def _select_smart_backend(monthly_product_data: pd.DataFrame) -> tuple[str, dict | None]:
    """Pick the backend with best holdout accuracy, or trend when history is short."""
    if len(monthly_product_data) < MIN_MONTHS_FOR_COMPARISON:
        return BACKEND_LINEAR_REGRESSION, None

    from logic.forecast_evaluation import compare_methods

    comparison = compare_methods(monthly_product_data)
    return comparison["winner_method_key"], comparison


def forecast_method_label(method: str) -> str:
    """User-facing label for a method or backend key."""
    return METHOD_DISPLAY_NAMES.get(method, "Smart Forecast")


def _predict_series(values: list[float], periods: int, backend_method: str) -> list[float]:
    return predict_quantity_series(values, periods, backend_method)


def _build_standard_forecast_result(
    monthly_product_data: pd.DataFrame,
    forecast_months: int,
    backend_method: str,
    ui_method: str | None = None,
) -> dict:
    if len(monthly_product_data) < MIN_HISTORY_MONTHS:
        raise ForecastError(
            f"Need at least {MIN_HISTORY_MONTHS} months of sales history to forecast. "
            f"This series only has {len(monthly_product_data)} month(s)."
        )

    forecast_months = max(1, forecast_months)
    build_periods = max(forecast_months, MAX_FORECAST_MONTHS)
    history_months = len(monthly_product_data)
    last_period = monthly_product_data["period"].iloc[-1]
    month_labels = _future_periods(last_period, build_periods)

    qty_values = [float(value) for value in monthly_product_data["quantity"].tolist()]
    qty_predictions = _predict_series(qty_values, build_periods, backend_method)

    money_predictions: list[float] | None = None
    profit_predictions: list[float] | None = None
    if "money_made" in monthly_product_data.columns:
        money_values = [float(value) for value in monthly_product_data["money_made"].tolist()]
        money_predictions = _predict_series(money_values, build_periods, backend_method)
    if "profit" in monthly_product_data.columns:
        profit_values = [float(value) for value in monthly_product_data["profit"].tolist()]
        profit_predictions = _predict_series(profit_values, build_periods, backend_method)

    forecast_entries: list[dict] = []
    for index in range(forecast_months):
        entry: dict = {
            "month": month_labels[index],
            "forecast_units": int(round(qty_predictions[index])),
            "expected_revenue": None,
            "expected_profit": None,
        }
        if money_predictions is not None:
            entry["expected_revenue"] = _round_number(money_predictions[index])
        if profit_predictions is not None:
            entry["expected_profit"] = _round_number(profit_predictions[index])
        forecast_entries.append(entry)

    if ui_method == METHOD_SMART_FORECAST:
        method_key = BACKEND_SMART_FORECAST
        display_name = METHOD_DISPLAY_NAMES[METHOD_SMART_FORECAST]
        explanation = METHOD_EXPLANATIONS[BACKEND_SMART_FORECAST]
    else:
        method_key = backend_method
        display_name = METHOD_DISPLAY_NAMES[backend_method]
        explanation = METHOD_EXPLANATIONS[backend_method]

    history_labels = [_period_label(period) for period in monthly_product_data["period"]]

    return {
        "method_key": method_key,
        "display_name": display_name,
        "forecast": forecast_entries,
        "confidence": _confidence_label(history_months),
        "explanation": explanation,
        "ui_method": ui_method or METHOD_TREND_FORECAST,
        "resolved_method_key": backend_method,
        "history_labels": history_labels,
        "history_units": [int(value) for value in qty_values],
        "history_money": (
            [_round_number(value) for value in monthly_product_data["money_made"].tolist()]
            if money_predictions is not None
            else None
        ),
        "history_profit": (
            [_round_number(value) for value in monthly_product_data["profit"].tolist()]
            if profit_predictions is not None
            else None
        ),
        "forecast_labels": [entry["month"] for entry in forecast_entries],
        "forecast_units": [entry["forecast_units"] for entry in forecast_entries],
        "forecast_money": (
            [entry["expected_revenue"] for entry in forecast_entries]
            if money_predictions is not None
            else None
        ),
        "forecast_profit": (
            [entry["expected_profit"] for entry in forecast_entries]
            if profit_predictions is not None
            else None
        ),
        "build_periods": build_periods,
    }


def forecast_linear_regression(
    monthly_product_data: pd.DataFrame,
    forecast_months: int,
) -> dict:
    """Trend forecast using linear regression on monthly product sales."""
    return _build_standard_forecast_result(
        monthly_product_data,
        forecast_months,
        BACKEND_LINEAR_REGRESSION,
        ui_method=METHOD_TREND_FORECAST,
    )


def forecast_moving_average(
    monthly_product_data: pd.DataFrame,
    forecast_months: int,
) -> dict:
    """Recent sales forecast using a rolling moving average."""
    return _build_standard_forecast_result(
        monthly_product_data,
        forecast_months,
        BACKEND_MOVING_AVERAGE,
        ui_method=METHOD_RECENT_SALES_FORECAST,
    )


def forecast_exponential_smoothing(
    monthly_product_data: pd.DataFrame,
    forecast_months: int,
) -> dict:
    """Smooth trend forecast using simple exponential smoothing."""
    return _build_standard_forecast_result(
        monthly_product_data,
        forecast_months,
        BACKEND_EXPONENTIAL_SMOOTHING,
    )


def forecast_random_forest(
    monthly_product_data: pd.DataFrame,
    forecast_months: int,
) -> dict:
    """Pattern forecast using a random forest on lagged monthly sales."""
    return _build_standard_forecast_result(
        monthly_product_data,
        forecast_months,
        BACKEND_RANDOM_FOREST,
    )


def run_forecast(
    monthly_product_data: pd.DataFrame,
    selected_product: str | None,
    forecast_months: int,
    method: str | None = None,
) -> dict:
    """
    Run the requested forecast method on monthly sales data.

    monthly_product_data: monthly aggregates (quantity, optional money_made, profit).
    selected_product: product name for context (may already be filtered into monthly data).
    forecast_months: number of future months to predict.
    method: UI method key (smart_forecast, trend_forecast, recent_sales_forecast).
    """
    ui_method = normalize_forecast_method(method)

    if ui_method == METHOD_SMART_FORECAST:
        backend_method, comparison = _select_smart_backend(monthly_product_data)
        result = _build_standard_forecast_result(
            monthly_product_data,
            forecast_months,
            backend_method,
            ui_method=METHOD_SMART_FORECAST,
        )
        chosen_display_name = (
            comparison["winner_display_name"]
            if comparison
            else METHOD_DISPLAY_NAMES[BACKEND_LINEAR_REGRESSION]
        )
        result["method_key"] = BACKEND_SMART_FORECAST
        result["display_name"] = METHOD_DISPLAY_NAMES[METHOD_SMART_FORECAST]
        result["explanation"] = (
            _smart_forecast_explanation(chosen_display_name)
            if comparison
            else _smart_forecast_fallback_explanation()
        )
        result["ui_method"] = METHOD_SMART_FORECAST
        result["resolved_method_key"] = backend_method
        result["chosen_method_display_name"] = chosen_display_name
        result["method_comparison"] = comparison
        result["selected_product"] = selected_product
        try:
            from logic.forecast_tracking import get_forecast_source_file, log_smart_forecast_run

            log_smart_forecast_run(
                result,
                forecast_periods=forecast_months,
                history_months=len(monthly_product_data),
                source_file=get_forecast_source_file(),
            )
        except Exception:
            pass
    elif ui_method == METHOD_RECENT_SALES_FORECAST:
        result = forecast_moving_average(monthly_product_data, forecast_months)
    elif ui_method == METHOD_TREND_FORECAST:
        result = forecast_linear_regression(monthly_product_data, forecast_months)
    else:
        result = forecast_linear_regression(monthly_product_data, forecast_months)

    result["selected_product"] = selected_product
    return result
