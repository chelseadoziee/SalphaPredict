"""Persistent SQLite logging for Smart Forecast runs and accuracy tracking."""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

import config
from logic.forecast_methods import (
    BACKEND_SMART_FORECAST,
    HOLDOUT_MONTHS,
    METHOD_SMART_FORECAST,
)
from logic.sales_analyser import _validate_sales_dataframe

DEFAULT_DB_PATH = config.DATABASE_PATH

_forecast_source_file: ContextVar[str | None] = ContextVar(
    "forecast_source_file",
    default=None,
)
_recent_log_guard: dict[tuple[str, str, int, str, str], float] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _period_label(period: pd.Period) -> str:
    return str(period)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percentage_error(actual: float, predicted: float) -> float | None:
    if actual == 0:
        return None
    return abs(actual - predicted) / abs(actual) * 100.0


@contextmanager
def forecast_logging_scope(source_file: str | None) -> Iterator[None]:
    """Attach the active cleaned data file to Smart Forecast tracking for this request."""
    token = _forecast_source_file.set(source_file)
    try:
        yield
    finally:
        _forecast_source_file.reset(token)


def get_forecast_source_file() -> str | None:
    return _forecast_source_file.get()


def build_forecast_log_dedupe_key(
    *,
    source_file: str | None,
    product: str | None,
    forecast_periods: int,
    ui_method: str,
    resolved_backend_method: str | None,
) -> tuple[str, str, int, str, str]:
    """Identity for duplicate Smart Forecast log suppression."""
    return (
        (source_file or "").strip().lower(),
        (product or "").strip(),
        int(forecast_periods),
        ui_method.strip().lower(),
        (resolved_backend_method or "").strip().lower(),
    )


def _prune_recent_log_guard(now: float, window_seconds: float) -> None:
    stale_keys = [
        key
        for key, logged_at in _recent_log_guard.items()
        if now - logged_at >= window_seconds
    ]
    for key in stale_keys:
        _recent_log_guard.pop(key, None)


def is_duplicate_forecast_log(
    dedupe_key: tuple[str, str, int, str, str],
    *,
    window_seconds: float | None = None,
) -> bool:
    """
    Return True when the same Smart Forecast run was logged recently in this process.

    A matching log within the dedupe window is treated as a refresh duplicate and skipped.
    """
    window = (
        float(window_seconds)
        if window_seconds is not None
        else float(config.FORECAST_LOG_DEDUPE_SECONDS)
    )
    now = time.monotonic()
    _prune_recent_log_guard(now, window)
    last_logged = _recent_log_guard.get(dedupe_key)
    if last_logged is not None and (now - last_logged) < window:
        return True
    _recent_log_guard[dedupe_key] = now
    return False


def clear_recent_log_guard() -> None:
    """Reset in-memory duplicate guard (for tests)."""
    _recent_log_guard.clear()


def _ensure_forecast_runs_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(forecast_runs)").fetchall()
    }
    if "source_file" not in columns:
        connection.execute("ALTER TABLE forecast_runs ADD COLUMN source_file TEXT")


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection with schema initialized."""
    path = Path(db_path or DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        init_forecast_tracking_db(connection)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_forecast_tracking_db(connection: sqlite3.Connection | None = None) -> None:
    """Create forecast tracking tables if they do not exist."""
    if connection is None:
        with get_connection() as conn:
            return

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS forecast_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ran_at TEXT NOT NULL,
            product TEXT,
            forecast_periods INTEGER NOT NULL,
            selected_backend_method TEXT NOT NULL,
            selected_display_name TEXT NOT NULL,
            confidence TEXT,
            history_months INTEGER NOT NULL,
            holdout_months INTEGER,
            winner_mae REAL,
            winner_rmse REAL,
            winner_mape REAL
        );

        CREATE TABLE IF NOT EXISTS forecast_model_comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            forecast_run_id INTEGER NOT NULL,
            backend_method TEXT NOT NULL,
            display_name TEXT NOT NULL,
            mae REAL NOT NULL,
            rmse REAL NOT NULL,
            mape REAL,
            rank INTEGER NOT NULL,
            is_winner INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (forecast_run_id) REFERENCES forecast_runs (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS forecast_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            forecast_run_id INTEGER NOT NULL,
            forecast_month TEXT NOT NULL,
            forecast_units REAL NOT NULL,
            expected_revenue REAL,
            expected_profit REAL,
            actual_units REAL,
            actual_revenue REAL,
            actual_profit REAL,
            unit_error REAL,
            percentage_error REAL,
            actual_recorded_at TEXT,
            FOREIGN KEY (forecast_run_id) REFERENCES forecast_runs (id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_forecast_predictions_month
            ON forecast_predictions (forecast_month);
        CREATE INDEX IF NOT EXISTS idx_forecast_predictions_actual_pending
            ON forecast_predictions (actual_units);
        CREATE INDEX IF NOT EXISTS idx_forecast_runs_product
            ON forecast_runs (product);
        """
    )
    if connection is not None:
        _ensure_forecast_runs_columns(connection)


def log_smart_forecast_run(
    standard_result: dict,
    *,
    forecast_periods: int,
    history_months: int,
    source_file: str | None = None,
    db_path: Path | None = None,
) -> int | None:
    """
    Persist a Smart Forecast run, its model comparison, and future predictions.

    Returns the new forecast_run id, or None if skipped or not a Smart Forecast run.
    """
    if standard_result.get("ui_method") != METHOD_SMART_FORECAST:
        return None
    if standard_result.get("method_key") != BACKEND_SMART_FORECAST:
        return None

    resolved_method = standard_result.get("resolved_method_key")
    source = source_file if source_file is not None else get_forecast_source_file()
    dedupe_key = build_forecast_log_dedupe_key(
        source_file=source,
        product=standard_result.get("selected_product"),
        forecast_periods=forecast_periods,
        ui_method=METHOD_SMART_FORECAST,
        resolved_backend_method=resolved_method,
    )
    if is_duplicate_forecast_log(dedupe_key):
        return None

    comparison = standard_result.get("method_comparison")
    winner = comparison.get("winner") if comparison else None

    with get_connection(db_path) as connection:
        _ensure_forecast_runs_columns(connection)
        cursor = connection.execute(
            """
            INSERT INTO forecast_runs (
                ran_at,
                product,
                forecast_periods,
                selected_backend_method,
                selected_display_name,
                confidence,
                history_months,
                holdout_months,
                winner_mae,
                winner_rmse,
                winner_mape,
                source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_now_iso(),
                standard_result.get("selected_product"),
                int(forecast_periods),
                resolved_method,
                standard_result.get("chosen_method_display_name")
                or standard_result.get("display_name"),
                standard_result.get("confidence"),
                int(history_months),
                comparison.get("holdout_months") if comparison else None,
                winner.get("mae") if winner else None,
                winner.get("rmse") if winner else None,
                winner.get("mape") if winner else None,
                source,
            ),
        )
        run_id = int(cursor.lastrowid)

        if comparison:
            for row in comparison.get("results", []):
                connection.execute(
                    """
                    INSERT INTO forecast_model_comparisons (
                        forecast_run_id,
                        backend_method,
                        display_name,
                        mae,
                        rmse,
                        mape,
                        rank,
                        is_winner
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        row["method_key"],
                        row["display_name"],
                        row["mae"],
                        row["rmse"],
                        row.get("mape"),
                        row["rank"],
                        1 if row["method_key"] == comparison.get("winner_method_key") else 0,
                    ),
                )

        for entry in standard_result.get("forecast", []):
            connection.execute(
                """
                INSERT INTO forecast_predictions (
                    forecast_run_id,
                    forecast_month,
                    forecast_units,
                    expected_revenue,
                    expected_profit
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    entry["month"],
                    float(entry["forecast_units"]),
                    _safe_float(entry.get("expected_revenue")),
                    _safe_float(entry.get("expected_profit")),
                ),
            )

        return run_id


def _monthly_actuals_lookup(
    cleaned_sales_df: pd.DataFrame,
) -> dict[tuple[str | None, str], dict[str, float | None]]:
    """
    Build {(product or None for all products, period_label): actual metrics}.
    """
    from logic.forecasting_engine import (
        prepare_monthly_product_series,
        prepare_monthly_totals,
    )

    working = _validate_sales_dataframe(cleaned_sales_df.copy())
    lookup: dict[tuple[str | None, str], dict[str, float | None]] = {}

    overall_monthly = prepare_monthly_totals(working)
    for _, row in overall_monthly.iterrows():
        period_label = _period_label(row["period"])
        lookup[(None, period_label)] = {
            "actual_units": float(row["quantity"]),
            "actual_revenue": _safe_float(row.get("money_made")),
            "actual_profit": _safe_float(row.get("profit")),
        }

    for product in working["product"].dropna().unique():
        product_name = str(product)
        product_monthly = prepare_monthly_product_series(working, product_name)
        for _, row in product_monthly.iterrows():
            period_label = _period_label(row["period"])
            lookup[(product_name, period_label)] = {
                "actual_units": float(row["quantity"]),
                "actual_revenue": _safe_float(row.get("money_made")),
                "actual_profit": _safe_float(row.get("profit")),
            }

    return lookup


def update_forecast_actuals(
    cleaned_sales_df: pd.DataFrame,
    db_path: Path | None = None,
) -> dict[str, int]:
    """
    Fill in actual sales for forecast months that now have observed data.

    Returns counts of rows updated and still pending actuals.
    """
    actuals_lookup = _monthly_actuals_lookup(cleaned_sales_df)
    recorded_at = _utc_now_iso()
    updated_rows = 0

    with get_connection(db_path) as connection:
        pending = connection.execute(
            """
            SELECT
                p.id AS prediction_id,
                p.forecast_month,
                p.forecast_units,
                r.product
            FROM forecast_predictions p
            JOIN forecast_runs r ON r.id = p.forecast_run_id
            WHERE p.actual_units IS NULL
            """
        ).fetchall()

        for row in pending:
            key = (row["product"], row["forecast_month"])
            actuals = actuals_lookup.get(key)
            if actuals is None:
                continue

            forecast_units = float(row["forecast_units"])
            actual_units = float(actuals["actual_units"])
            unit_error = abs(actual_units - forecast_units)
            pct_error = _percentage_error(actual_units, forecast_units)

            connection.execute(
                """
                UPDATE forecast_predictions
                SET
                    actual_units = ?,
                    actual_revenue = ?,
                    actual_profit = ?,
                    unit_error = ?,
                    percentage_error = ?,
                    actual_recorded_at = ?
                WHERE id = ?
                """,
                (
                    actual_units,
                    actuals.get("actual_revenue"),
                    actuals.get("actual_profit"),
                    unit_error,
                    pct_error,
                    recorded_at,
                    row["prediction_id"],
                ),
            )
            updated_rows += 1

        still_pending = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM forecast_predictions
            WHERE actual_units IS NULL
            """
        ).fetchone()["count"]

    return {
        "predictions_updated": updated_rows,
        "predictions_still_pending": int(still_pending),
    }


def get_forecast_evaluation_summary(db_path: Path | None = None) -> dict[str, Any]:
    """Internal summary of forecast logging and measured accuracy."""
    with get_connection(db_path) as connection:
        total_runs = connection.execute(
            "SELECT COUNT(*) AS count FROM forecast_runs"
        ).fetchone()["count"]

        error_row = connection.execute(
            """
            SELECT
                AVG(unit_error) AS avg_unit_error,
                AVG(percentage_error) AS avg_percentage_error
            FROM forecast_predictions
            WHERE actual_units IS NOT NULL
            """
        ).fetchone()

        best_method_row = connection.execute(
            """
            SELECT
                r.selected_backend_method AS method_key,
                r.selected_display_name AS display_name,
                AVG(p.percentage_error) AS avg_pct_error
            FROM forecast_predictions p
            JOIN forecast_runs r ON r.id = p.forecast_run_id
            WHERE p.percentage_error IS NOT NULL
            GROUP BY r.selected_backend_method, r.selected_display_name
            ORDER BY avg_pct_error ASC
            LIMIT 1
            """
        ).fetchone()

        most_selected_row = connection.execute(
            """
            SELECT
                selected_backend_method AS method_key,
                selected_display_name AS display_name,
                COUNT(*) AS selection_count
            FROM forecast_runs
            GROUP BY selected_backend_method, selected_display_name
            ORDER BY selection_count DESC
            LIMIT 1
            """
        ).fetchone()

        highest_error_products = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    COALESCE(r.product, 'All products') AS product,
                    AVG(p.percentage_error) AS avg_percentage_error,
                    AVG(p.unit_error) AS avg_unit_error,
                    COUNT(*) AS evaluated_predictions
                FROM forecast_predictions p
                JOIN forecast_runs r ON r.id = p.forecast_run_id
                WHERE p.percentage_error IS NOT NULL
                GROUP BY r.product
                ORDER BY avg_percentage_error DESC
                LIMIT 10
                """
            ).fetchall()
        ]

        holdout_best_row = connection.execute(
            """
            SELECT
                backend_method AS method_key,
                display_name,
                AVG(mape) AS avg_holdout_mape
            FROM forecast_model_comparisons
            WHERE mape IS NOT NULL AND is_winner = 1
            GROUP BY backend_method, display_name
            ORDER BY avg_holdout_mape ASC
            LIMIT 1
            """
        ).fetchone()

        pending_predictions = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM forecast_predictions
            WHERE actual_units IS NULL
            """
        ).fetchone()["count"]

        pending_runs = connection.execute(
            """
            SELECT COUNT(DISTINCT forecast_run_id) AS count
            FROM forecast_predictions
            WHERE actual_units IS NULL
            """
        ).fetchone()["count"]

    return {
        "total_forecasts_run": int(total_runs),
        "average_unit_error": _safe_float(error_row["avg_unit_error"]),
        "average_percentage_error": _safe_float(error_row["avg_percentage_error"]),
        "best_performing_method": (
            {
                "method_key": best_method_row["method_key"],
                "display_name": best_method_row["display_name"],
                "avg_percentage_error": _safe_float(best_method_row["avg_pct_error"]),
            }
            if best_method_row
            else None
        ),
        "best_holdout_winner_method": (
            {
                "method_key": holdout_best_row["method_key"],
                "display_name": holdout_best_row["display_name"],
                "avg_holdout_mape": _safe_float(holdout_best_row["avg_holdout_mape"]),
            }
            if holdout_best_row
            else None
        ),
        "most_selected_method": (
            {
                "method_key": most_selected_row["method_key"],
                "display_name": most_selected_row["display_name"],
                "selection_count": int(most_selected_row["selection_count"]),
            }
            if most_selected_row
            else None
        ),
        "products_with_highest_forecast_error": highest_error_products,
        "predictions_waiting_for_actuals": int(pending_predictions),
        "forecast_runs_waiting_for_actuals": int(pending_runs),
    }
