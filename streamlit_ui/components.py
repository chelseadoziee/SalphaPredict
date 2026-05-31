from __future__ import annotations

import html
from typing import Any

import streamlit as st

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
