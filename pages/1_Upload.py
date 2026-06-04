from __future__ import annotations

import html

import streamlit as st

import config
from logic.data_loader import UploadError
from streamlit_ui.components import page_header, render_html, upload_success_panel
from streamlit_ui.navigation import PROFIT_LOSS_PAGE, SALES_PAGE, STOCK_ADVICE_PAGE, page_button
from streamlit_ui.session import (
    clean_staged_upload,
    flash_error,
    flash_success,
    handle_new_upload,
    init_session_state,
)
from streamlit_ui.theme import configure_page, render_footer

config.ensure_directories()
configure_page("Upload")
init_session_state()

page_header(
    "Upload sales data",
    "Upload an Excel file to preview it, then clean it to unlock the dashboard. "
    "Supported formats: .xlsx and .xls.",
)

uploaded_file = st.file_uploader(
    "Choose Excel file",
    type=sorted(config.ALLOWED_EXTENSIONS),
    label_visibility="collapsed",
)

if uploaded_file is not None:
    try:
        handle_new_upload(uploaded_file)
    except UploadError as exc:
        flash_error(str(exc))

preview = st.session_state.get("upload_preview")
cleaning_report = st.session_state.get("cleaning_report")
preview_ready = bool(preview and preview.get("success"))
already_cleaned = bool(cleaning_report and cleaning_report.get("success"))

if preview_ready and not already_cleaned:
    render_html(
        '<p class="muted chart-caption">'
        "File uploaded. Review the preview below, then clean it to prepare analysis."
        "</p>"
    )

if preview_ready:
    render_html(
        f'<section class="preview-card dashboard-card">'
        f"<h2>Upload preview</h2>"
        f'<dl class="preview-meta">'
        f"<div><dt>Filename</dt><dd>{html.escape(preview['filename'])}</dd></div>"
        f"<div><dt>Rows</dt><dd>{preview['row_count']:,}</dd></div>"
        f"</dl>"
        f"<h3>Columns</h3>"
        f'<ul class="column-list">'
        f'{"".join(f"<li>{html.escape(column)}</li>" for column in preview["columns"])}'
        f"</ul>"
        f"</section>"
    )

if preview_ready and not already_cleaned:
    if st.button("Clean file", type="primary", key="clean_upload_btn"):
        try:
            if clean_staged_upload():
                flash_success("File cleaned successfully. You can open the dashboards below.")
                st.rerun()
            else:
                report = st.session_state.get("cleaning_report") or {}
                flash_error(report.get("error", "Could not clean the uploaded file."))
        except UploadError as exc:
            flash_error(str(exc))
elif preview and not preview.get("success"):
    flash_error(preview.get("error", "Could not preview the uploaded file."))

cleaning_report = st.session_state.get("cleaning_report")

if cleaning_report and cleaning_report.get("success"):
    filename = (
        preview["filename"]
        if preview and preview.get("filename")
        else cleaning_report.get("cleaned_filename", "File")
    )
    upload_success_panel(filename, cleaning_report.get("cleaned_rows", 0))

    col1, col2, col3 = st.columns(3)
    with col1:
        page_button("View product sales dashboard", SALES_PAGE, key="upload_sales")
    with col2:
        page_button("View profit & loss", PROFIT_LOSS_PAGE, key="upload_profit")
    with col3:
        page_button("View stock advice", STOCK_ADVICE_PAGE, key="upload_stock")

render_footer()
