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
        "staged_filepath": None,
        "last_staged_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def upload_file_id(uploaded_file) -> str:
    size = getattr(uploaded_file, "size", None)
    if size is None:
        try:
            size = len(uploaded_file.getvalue())
        except Exception:
            size = "unknown"
    return f"{uploaded_file.name}:{size}"


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
    filepath.write_bytes(uploaded_file.getvalue())
    return filepath


def _clear_clean_results() -> None:
    st.session_state["cleaning_report"] = None
    st.session_state["cleaned_path"] = None


def stage_upload(uploaded_file) -> bool:
    """Save the file and build a preview. Does not run cleaning."""
    filepath = save_uploaded_file(uploaded_file, config.UPLOAD_FOLDER)
    preview = preview_excel(filepath)

    st.session_state["staged_filepath"] = str(filepath)

    st.session_state["upload_preview"] = preview
    if not preview.get("success"):
        _clear_clean_results()
        return False
    _clear_clean_results()
    return True


def clean_staged_upload() -> bool:
    """Clean the file saved by :func:`stage_upload`. Returns True on success."""
    staged = st.session_state.get("staged_filepath")
    if not staged:
        raise UploadError("Upload a file first, then click Clean file.")

    filepath = Path(staged)
    if not filepath.exists():
        raise UploadError("The uploaded file is no longer available. Please upload it again.")

    preview = st.session_state.get("upload_preview")
    if not preview or not preview.get("success"):
        raise UploadError("Fix the upload preview issues before cleaning.")

    cleaning_report = clean_sales_file(filepath, config.DATA_FOLDER)
    st.session_state["cleaning_report"] = cleaning_report

    if not cleaning_report.get("success"):
        st.session_state["cleaned_path"] = None
        return False

    st.session_state["cleaned_path"] = config.DATA_FOLDER / cleaning_report["cleaned_filename"]
    return True


def handle_new_upload(uploaded_file) -> None:
    """Stage a newly selected file; skip work if it is already staged."""
    file_id = upload_file_id(uploaded_file)
    if st.session_state.get("last_staged_id") == file_id:
        return

    st.session_state["last_staged_id"] = file_id
    stage_upload(uploaded_file)


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
