from __future__ import annotations

import html

import streamlit as st

import config
from logic.data_loader import UploadError
from streamlit_ui.components import page_header, render_html, upload_success_panel
from streamlit_ui.navigation import PROFIT_LOSS_PAGE, SALES_PAGE, STOCK_ADVICE_PAGE, page_button
from streamlit_ui.session import flash_error, flash_success, init_session_state, process_upload
from streamlit_ui.theme import configure_page, render_footer

config.ensure_directories()
configure_page("Upload")
init_session_state()

page_header(
    "Upload sales data",
    "Upload an Excel file to clean your product sales data and open the dashboard. "
    "Supported formats: .xlsx and .xls.",
)

uploaded_file = st.file_uploader(
    "Choose Excel file",
    type=sorted(config.ALLOWED_EXTENSIONS),
    label_visibility="collapsed",
)

if uploaded_file is not None:
    try:
        if process_upload(uploaded_file):
            flash_success("File uploaded and cleaned successfully.")
        else:
            preview = st.session_state.get("upload_preview")
            cleaning_report = st.session_state.get("cleaning_report")
            if preview and not preview.get("success"):
                flash_error(preview.get("error", "Could not preview the uploaded file."))
            elif cleaning_report:
                flash_error(cleaning_report.get("error", "Could not clean the uploaded file."))
    except UploadError as exc:
        flash_error(str(exc))

preview = st.session_state.get("upload_preview")
cleaning_report = st.session_state.get("cleaning_report")

if preview and preview.get("success"):
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

if cleaning_report and cleaning_report.get("success"):
    filename = preview["filename"] if preview else cleaning_report.get("cleaned_filename", "File")
    upload_success_panel(filename, cleaning_report.get("cleaned_rows", 0))

    col1, col2, col3 = st.columns(3)
    with col1:
        page_button("View product sales dashboard", SALES_PAGE, key="upload_sales")
    with col2:
        page_button("View profit & loss", PROFIT_LOSS_PAGE, key="upload_profit")
    with col3:
        page_button("View stock advice", STOCK_ADVICE_PAGE, key="upload_stock")

render_footer()
