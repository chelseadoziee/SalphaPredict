from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

import config
from logic.data_cleaner import clean_sales_file
from logic.data_loader import UploadError, allowed_file, preview_excel, secure_filename
from streamlit_ui.components import render_html
from streamlit_ui.navigation import UPLOAD_PAGE, page_button


def init_session_state() -> None:
    defaults = {
        "upload_preview": None,
        "cleaning_report": None,
        "cleaned_path": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def save_uploaded_file(uploaded_file, upload_folder: Path) -> Path:
    if not uploaded_file or not uploaded_file.name:
        raise UploadError("No file selected. Please choose an Excel file to upload.")

    if not allowed_file(uploaded_file.name, config.ALLOWED_EXTENSIONS):
        raise UploadError("Invalid file type. Please upload a .xlsx or .xls file.")

    filename = secure_filename(uploaded_file.name)
    if not filename:
        raise UploadError("The selected filename is not valid.")

    upload_folder.mkdir(parents=True, exist_ok=True)
    filepath = upload_folder / filename
    filepath.write_bytes(uploaded_file.getbuffer())
    return filepath


def process_upload(uploaded_file) -> bool:
    """Save, preview, and clean an uploaded file. Returns True on success."""
    file_id = f"{uploaded_file.name}:{uploaded_file.size}"
    if st.session_state.get("last_upload_id") == file_id:
        return bool(st.session_state.get("cleaned_path"))

    try:
        filepath = save_uploaded_file(uploaded_file, config.UPLOAD_FOLDER)
        preview = preview_excel(filepath)

        if not preview.get("success"):
            st.session_state["upload_preview"] = None
            st.session_state["cleaning_report"] = None
            st.session_state["cleaned_path"] = None
            st.session_state["last_upload_id"] = None
            return False

        cleaning_report = clean_sales_file(filepath, config.DATA_FOLDER)
        st.session_state["upload_preview"] = preview
        st.session_state["cleaning_report"] = cleaning_report

        if not cleaning_report.get("success"):
            st.session_state["cleaned_path"] = None
            st.session_state["last_upload_id"] = None
            return False

        st.session_state["cleaned_path"] = config.DATA_FOLDER / cleaning_report["cleaned_filename"]
        st.session_state["last_upload_id"] = file_id
        return True

    except UploadError:
        st.session_state["last_upload_id"] = None
        raise


def require_cleaned_path() -> Path:
    init_session_state()
    cleaned_path = st.session_state.get("cleaned_path")
    if cleaned_path is None or not Path(cleaned_path).exists():
        render_html(
            '<div class="flash flash-error">'
            "Upload and clean a product data file before using this page."
            "</div>"
        )
        page_button("Go to Upload", UPLOAD_PAGE, key="require_upload")
        st.stop()
    return Path(cleaned_path)


def flash_success(message: str) -> None:
    render_html(f'<div class="flash flash-success">{html.escape(message)}</div>')


def flash_error(message: str) -> None:
    render_html(f'<div class="flash flash-error">{html.escape(message)}</div>')
