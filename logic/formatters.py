"""Shared display formatters for SalphaPredict templates."""

from __future__ import annotations


def format_naira_compact(value: float | int | None) -> str:
    """Format large naira amounts in a compact KPI-friendly style (e.g. ₦272.9M)."""
    if value is None:
        return "—"

    amount = float(value)
    if amount != amount:  # NaN
        return "—"

    sign = "-" if amount < 0 else ""
    abs_amount = abs(amount)

    if abs_amount >= 1_000_000_000:
        billions = abs_amount / 1_000_000_000
        rounded = f"{billions:.1f}".rstrip("0").rstrip(".")
        return f"{sign}₦{rounded}B"

    if abs_amount >= 1_000_000:
        millions = abs_amount / 1_000_000
        rounded = f"{millions:.1f}".rstrip("0").rstrip(".")
        return f"{sign}₦{rounded}M"

    if abs_amount >= 1_000:
        thousands = abs_amount / 1_000
        rounded = f"{thousands:.1f}".rstrip("0").rstrip(".")
        return f"{sign}₦{rounded}K"

    return f"{sign}₦{abs_amount:,.0f}"


def format_naira_full(value: float | int | None) -> str:
    """Format naira with full precision for tooltips and tables."""
    if value is None:
        return "—"
    amount = float(value)
    if amount != amount:
        return "—"
    return f"₦{amount:,.2f}"
