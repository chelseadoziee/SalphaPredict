from __future__ import annotations

import html
from typing import Any

import streamlit as st

import config
from logic.formatters import format_naira_compact, format_naira_full


def render_html(body: str) -> None:
    """Render HTML without Markdown treating indented tags as code blocks."""
    st.html(body)


def page_header(title: str, subtitle: str) -> None:
    render_html(
        f'<section class="page-header">'
        f'<h1 class="h1-page">{html.escape(title)}</h1>'
        f"<p>{subtitle}</p>"
        f"</section>"
    )


def kpi_grid(items: list[dict[str, Any]]) -> None:
    cards = []
    for item in items:
        label = html.escape(str(item["label"]))
        value = item["value"]
        if isinstance(value, (int, float)) and item.get("money"):
            display = html.escape(format_naira_compact(value))
            title_attr = f' title="{html.escape(format_naira_full(value))}"'
            value_class = "kpi-value kpi-value-money"
        elif item.get("text_value"):
            display = html.escape(str(value))
            title_attr = ""
            value_class = "kpi-value kpi-value-text"
        else:
            display = html.escape(str(value))
            title_attr = ""
            value_class = "kpi-value"

        trend = item.get("trend_class")
        if trend:
            value_class += f" trend-{html.escape(trend)}"

        sub_html = ""
        if item.get("sub"):
            sub_html = f'<p class="kpi-sub">{html.escape(str(item["sub"]))}</p>'

        cards.append(
            f'<article class="kpi-card">'
            f'<p class="kpi-label">{label}</p>'
            f'<p class="{value_class}"{title_attr}>{display}</p>'
            f"{sub_html}"
            f"</article>"
        )

    render_html(f'<section class="kpi-grid">{"".join(cards)}</section>')


def insight_summary(title: str, paragraphs: list[str]) -> None:
    body = "".join(
        f'<p class="summary-text">{html.escape(paragraph)}</p>' for paragraph in paragraphs
    )
    render_html(
        f'<section class="dashboard-card insight-summary">'
        f"<h2>{html.escape(title)}</h2>"
        f"{body}"
        f"</section>"
    )


def notice_card(message: str) -> None:
    render_html(
        f'<section class="dashboard-card notice-card">'
        f'<p class="summary-text">{html.escape(message)}</p>'
        f"</section>"
    )


def smart_forecast_panel(forecast_report: dict[str, Any]) -> None:
    """Render Smart Forecast summary aligned with the Flask forecast page."""
    explanation = forecast_report.get("forecast_explanation") or ""
    chosen = forecast_report.get("chosen_method_display_name")
    focus = forecast_report.get("product_focus") or {}
    summary = forecast_report.get("summary") or {}

    if forecast_report.get("view_mode") == "product_journey" and focus:
        confidence = focus.get("forecast_confidence", "N/A")
        confidence_detail = focus.get("forecast_confidence_detail") or ""
    else:
        confidence = summary.get("forecast_confidence", "N/A")
        confidence_detail = summary.get("forecast_confidence_detail") or ""

    confidence_html = f"<strong>{html.escape(str(confidence))}</strong>"
    if confidence_detail:
        confidence_html += (
            f' <span class="muted">· {html.escape(str(confidence_detail))}</span>'
        )

    method_html = ""
    if chosen:
        method_html = (
            '<div class="smart-forecast-meta-item">'
            "<dt>Method in use</dt>"
            f"<dd><strong>{html.escape(chosen)}</strong></dd>"
            "</div>"
        )

    pills = forecast_report.get("smart_forecast_methods_tested") or []
    pills_html = ""
    if pills:
        pill_items = "".join(
            f'<li class="smart-method-pill{" is-active" if chosen == item["label"] else ""}">'
            f'{html.escape(item["label"])}</li>'
            for item in pills
        )
        pills_html = (
            '<p class="muted chart-caption smart-methods-caption">'
            "Methods compared when enough history is available:</p>"
            f'<ul class="smart-method-pills" aria-label="Forecast methods tested">{pill_items}</ul>'
        )

    render_html(
        f'<section class="dashboard-card smart-forecast-card">'
        f'<div class="smart-forecast-header">'
        f"<h2>Smart Forecast</h2>"
        f'<span class="smart-forecast-badge">Automatic</span>'
        f"</div>"
        f'<p class="summary-text smart-forecast-explanation">{html.escape(explanation)}</p>'
        f'<dl class="smart-forecast-meta">'
        f"{method_html}"
        f'<div class="smart-forecast-meta-item">'
        f"<dt>Confidence</dt><dd>{confidence_html}</dd>"
        f"</div>"
        f'<div class="smart-forecast-meta-item">'
        f"<dt>Sales history</dt>"
        f'<dd>{int(forecast_report.get("history_months", 0))} months in this view</dd>'
        f"</div>"
        f"</dl>"
        f"{pills_html}"
        f"</section>"
    )


def _metric_help_header_html(metric_key: str, metric_help: dict[str, dict[str, str]]) -> str:
    help_info = metric_help[metric_key]
    label = html.escape(help_info["label"])
    title = html.escape(help_info["title"])
    description = html.escape(help_info["description"])
    aria = html.escape(f'{help_info["label"]}: {help_info["title"]}. {help_info["description"]}')
    native_title = html.escape(f'{help_info["title"]}. {help_info["description"]}')
    return (
        f'<th class="metric-help-header" scope="col">'
        f'<span class="metric-help-trigger" tabindex="0"'
        f' data-metric-title="{title}" data-metric-text="{description}"'
        f' title="{native_title}" aria-label="{aria}">{label}</span></th>'
    )


def _inject_metric_tooltip_script() -> None:
    script_path = config.BASE_DIR / "static" / "js" / "metric-tooltips.js"
    script_body = script_path.read_text(encoding="utf-8")
    render_html(f"<script>{script_body}</script>")


def method_comparison_panel(comparison: dict[str, Any] | None) -> None:
    """Collapsible holdout comparison table for Smart Forecast."""
    if not comparison:
        return

    metric_help = comparison.get("metric_help")
    if not metric_help:
        from logic.forecast_evaluation import HOLDOUT_METRIC_HELP

        metric_help = HOLDOUT_METRIC_HELP

    metric_headers = "".join(
        _metric_help_header_html(key, metric_help) for key in ("mae", "rmse", "mape")
    )

    rows_html = []
    for row in comparison.get("rows", []):
        row_class = "method-comparison-winner" if row.get("is_winner") else ""
        name = row["display_name"]
        if row.get("is_winner"):
            name = f"{name} (selected)"
        mape = f'{row["mape"]}%' if row.get("mape") is not None else "N/A"
        rows_html.append(
            f'<tr class="{row_class}">'
            f'<td>{html.escape(str(row["rank"]))}</td>'
            f"<td>{html.escape(name)}</td>"
            f'<td>{html.escape(str(row["mae"]))}</td>'
            f'<td>{html.escape(str(row["rmse"]))}</td>'
            f"<td>{html.escape(mape)}</td>"
            f"</tr>"
        )

    render_html(
        f'<details class="dashboard-card method-comparison-details" open>'
        f'<summary class="method-comparison-summary">'
        f"How Smart Forecast chose "
        f'<span class="method-comparison-summary-hint">Holdout test · lower error is better</span>'
        f"</summary>"
        f'<p class="muted chart-caption">'
        f'Each method was scored on the last {comparison["holdout_months"]} months of sales. '
        f'Training used {comparison["train_months"]} months '
        f'({html.escape(comparison["train_period_start"])} to '
        f'{html.escape(comparison["train_period_end"])}). '
        f'Smart Forecast selected <strong>{html.escape(comparison["chosen_display_name"])}</strong>.'
        f"</p>"
        f'<div class="table-wrap"><table class="data-table method-comparison-table">'
        f'<thead><tr><th scope="col">Rank</th><th scope="col">Method</th>'
        f"{metric_headers}</tr></thead>"
        f'<tbody>{"".join(rows_html)}</tbody></table></div>'
        f"</details>"
    )
    _inject_metric_tooltip_script()


def section_card(title: str, caption: str | None = None, highlight: bool = False) -> None:
    classes = "dashboard-card"
    if highlight:
        classes += " highlight-card"
    caption_html = ""
    if caption:
        caption_html = f'<p class="muted chart-caption">{html.escape(caption)}</p>'
    render_html(
        f'<section class="{classes}">'
        f"<h2>{html.escape(title)}</h2>"
        f"{caption_html}"
        f"</section>"
    )


def chart_card(title: str, caption: str) -> None:
    render_html(
        f'<article class="dashboard-card chart-card streamlit-chart-card">'
        f"<h2>{html.escape(title)}</h2>"
        f'<p class="muted chart-caption">{html.escape(caption)}</p>'
        f"</article>"
    )


def render_table(headers: list[str], rows: list[list[Any]]) -> None:
    head = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = []
        for cell in row:
            if isinstance(cell, dict):
                cells.append(cell["html"])
            else:
                cells.append(html.escape(str(cell)))
        body_rows.append(f"<tr>{''.join(f'<td>{cell}</td>' for cell in cells)}</tr>")

    render_html(
        f'<div class="table-wrap">'
        f'<table class="data-table">'
        f"<thead><tr>{head}</tr></thead>"
        f'<tbody>{"".join(body_rows)}</tbody>'
        f"</table>"
        f"</div>"
    )


def priority_badge(label: str, priority: str) -> dict:
    safe_label = html.escape(label)
    safe_priority = html.escape(priority)
    return {
        "html": (
            f'<span class="priority-badge priority-{safe_priority}">{safe_label}</span>'
        )
    }


def action_priority(action: str) -> str:
    if action == "Restock regularly":
        return "high"
    if action in {"Track closely", "Keep stable"}:
        return "medium"
    return "low"


def money_cell(value: float | int | None, compact: bool = False) -> str:
    if value is None:
        return "—"
    if compact:
        return format_naira_compact(value)
    return f"₦{float(value):,.2f}"


def advice_list(items: list[str]) -> None:
    if not items:
        render_html('<p class="muted">No items to show.</p>')
        return
    list_html = "".join(f"<li>{html.escape(item)}</li>" for item in items)
    render_html(f'<ul class="stock-advice-list">{list_html}</ul>')


def feature_grid(cards: list[tuple[str, str]]) -> None:
    items = "".join(
        f'<article class="feature-card">'
        f"<h2>{html.escape(title)}</h2>"
        f"<p>{html.escape(text)}</p>"
        f"</article>"
        for title, text in cards
    )
    render_html(f'<section class="feature-grid">{items}</section>')


def upload_success_panel(filename: str, cleaned_rows: int) -> None:
    render_html(
        f'<section class="upload-panel upload-success">'
        f"<h2>Ready to view</h2>"
        f"<p><strong>{html.escape(filename)}</strong> was uploaded and cleaned successfully.</p>"
        f'<p class="muted">{cleaned_rows:,} rows are ready for analysis.</p>'
        f"</section>"
    )
