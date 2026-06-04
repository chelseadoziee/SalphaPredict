from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import pytest

from logic.forecast_methods import METHOD_SMART_FORECAST, run_forecast
from logic.forecast_tracking import (
    build_forecast_log_dedupe_key,
    clear_recent_log_guard,
    forecast_logging_scope,
    get_connection,
    get_forecast_evaluation_summary,
    init_forecast_tracking_db,
    is_duplicate_forecast_log,
    log_smart_forecast_run,
    update_forecast_actuals,
)


@pytest.fixture(autouse=True)
def _reset_log_guard():
    clear_recent_log_guard()
    yield
    clear_recent_log_guard()


def _monthly_series(months: int = 10) -> pd.DataFrame:
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


def _sales_df(months: int = 10) -> pd.DataFrame:
    rows = []
    for month in range(1, months + 1):
        period = f"2025-{month:02d}-15"
        rows.append(
            {
                "sale_date": period,
                "product": "Spark",
                "quantity": 20 + month,
                "total_amount": (20 + month) * 80000,
                "profit": (20 + month) * 10000,
            }
        )
    return pd.DataFrame(rows)


def test_log_smart_forecast_run_persists_run_comparison_and_predictions(tmp_path: Path):
    db_path = tmp_path / "tracking.sqlite3"
    monthly = _monthly_series(10)
    with forecast_logging_scope("sales_cleaned.csv"):
        result = run_forecast(monthly, "Spark", 3, METHOD_SMART_FORECAST)
    clear_recent_log_guard()

    run_id = log_smart_forecast_run(
        result,
        forecast_periods=3,
        history_months=len(monthly),
        source_file="sales_cleaned.csv",
        db_path=db_path,
    )

    assert run_id == 1

    with get_connection(db_path) as connection:
        run = connection.execute(
            "SELECT * FROM forecast_runs WHERE id = ?", (run_id,)
        ).fetchone()
        comparisons = connection.execute(
            "SELECT * FROM forecast_model_comparisons WHERE forecast_run_id = ?",
            (run_id,),
        ).fetchall()
        predictions = connection.execute(
            "SELECT * FROM forecast_predictions WHERE forecast_run_id = ?",
            (run_id,),
        ).fetchall()

    assert run["product"] == "Spark"
    assert run["forecast_periods"] == 3
    assert run["selected_backend_method"] == result["resolved_method_key"]
    assert run["selected_display_name"] == result["chosen_method_display_name"]
    assert run["confidence"] == result["confidence"]
    assert run["history_months"] == 10
    assert run["holdout_months"] == 3
    assert run["winner_mae"] is not None

    assert len(comparisons) == 4
    assert sum(row["is_winner"] for row in comparisons) == 1

    assert len(predictions) == 3
    assert all(row["actual_units"] is None for row in predictions)


def test_run_forecast_smart_writes_tracking_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "auto.sqlite3"
    monkeypatch.setattr("logic.forecast_tracking.DEFAULT_DB_PATH", db_path)

    monthly = _monthly_series(10)
    with forecast_logging_scope("sales_cleaned.csv"):
        run_forecast(monthly, None, 3, METHOD_SMART_FORECAST)

    with get_connection(db_path) as connection:
        count = connection.execute("SELECT COUNT(*) AS c FROM forecast_runs").fetchone()["c"]
    assert count == 1


def test_duplicate_guard_skips_identical_refresh_within_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db_path = tmp_path / "dedupe.sqlite3"
    monkeypatch.setattr("logic.forecast_tracking.DEFAULT_DB_PATH", db_path)
    monthly = _monthly_series(10)
    with forecast_logging_scope("sales_cleaned.csv"):
        first = run_forecast(monthly, None, 3, METHOD_SMART_FORECAST)
        second = run_forecast(monthly, None, 3, METHOD_SMART_FORECAST)

    assert first["resolved_method_key"] == second["resolved_method_key"]

    with get_connection(db_path) as connection:
        count = connection.execute("SELECT COUNT(*) AS c FROM forecast_runs").fetchone()["c"]
    assert count == 1


def test_duplicate_guard_allows_different_product_or_period(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db_path = tmp_path / "dedupe_variants.sqlite3"
    monkeypatch.setattr("logic.forecast_tracking.DEFAULT_DB_PATH", db_path)
    monthly = _monthly_series(10)

    with forecast_logging_scope("sales_cleaned.csv"):
        run_forecast(monthly, None, 3, METHOD_SMART_FORECAST)
        run_forecast(monthly, "Spark", 3, METHOD_SMART_FORECAST)
        run_forecast(monthly, None, 6, METHOD_SMART_FORECAST)

    with get_connection(db_path) as connection:
        count = connection.execute("SELECT COUNT(*) AS c FROM forecast_runs").fetchone()["c"]
    assert count == 3


def test_is_duplicate_forecast_log_expires_after_window():
    from logic import forecast_tracking

    key = build_forecast_log_dedupe_key(
        source_file="sales_cleaned.csv",
        product=None,
        forecast_periods=3,
        ui_method=METHOD_SMART_FORECAST,
        resolved_backend_method="linear_regression",
    )
    assert is_duplicate_forecast_log(key, window_seconds=60) is False
    assert is_duplicate_forecast_log(key, window_seconds=60) is True

    forecast_tracking._recent_log_guard[key] = time.monotonic() - 120
    assert is_duplicate_forecast_log(key, window_seconds=60) is False


def test_update_forecast_actuals_fills_matching_months(tmp_path: Path):
    db_path = tmp_path / "tracking.sqlite3"
    monthly = _monthly_series(10)
    with forecast_logging_scope("sales_cleaned.csv"):
        result = run_forecast(monthly, "Spark", 3, METHOD_SMART_FORECAST)
    clear_recent_log_guard()
    log_smart_forecast_run(
        result,
        forecast_periods=3,
        history_months=10,
        source_file="sales_cleaned.csv",
        db_path=db_path,
    )

    with get_connection(db_path) as connection:
        future_month = connection.execute(
            """
            SELECT forecast_month
            FROM forecast_predictions
            WHERE actual_units IS NULL
            LIMIT 1
            """
        ).fetchone()["forecast_month"]

    month_number = int(str(future_month).split("-")[1])
    sales = _sales_df(months=max(month_number, 10))

    stats = update_forecast_actuals(sales, db_path=db_path)

    assert stats["predictions_updated"] >= 1

    with get_connection(db_path) as connection:
        updated = connection.execute(
            """
            SELECT actual_units, unit_error, percentage_error, actual_recorded_at
            FROM forecast_predictions
            WHERE forecast_month = ?
            """,
            (future_month,),
        ).fetchone()

    assert updated["actual_units"] is not None
    assert updated["unit_error"] is not None
    assert updated["percentage_error"] is not None
    assert updated["actual_recorded_at"] is not None


def test_get_forecast_evaluation_summary(tmp_path: Path):
    db_path = tmp_path / "summary.sqlite3"
    monthly = _monthly_series(10)
    with forecast_logging_scope("sales_cleaned.csv"):
        result = run_forecast(monthly, None, 2, METHOD_SMART_FORECAST)
    clear_recent_log_guard()
    log_smart_forecast_run(
        result,
        forecast_periods=2,
        history_months=10,
        source_file="sales_cleaned.csv",
        db_path=db_path,
    )

    summary = get_forecast_evaluation_summary(db_path=db_path)

    assert summary["total_forecasts_run"] == 1
    assert summary["most_selected_method"] is not None
    assert summary["predictions_waiting_for_actuals"] == 2
    assert summary["forecast_runs_waiting_for_actuals"] == 1
    assert summary["average_unit_error"] is None


def test_init_forecast_tracking_db_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "init.sqlite3"
    connection = __import__("sqlite3").connect(db_path)
    init_forecast_tracking_db(connection)
    init_forecast_tracking_db(connection)
    connection.close()
