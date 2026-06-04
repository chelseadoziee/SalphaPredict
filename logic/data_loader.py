from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

_FILENAME_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class UploadError(Exception):
    """Raised when an uploaded file fails validation or cannot be saved."""


def secure_filename(filename: str) -> str:
    """Return a safe basename for storing an uploaded file (no path segments)."""
    name = Path(filename).name
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = _FILENAME_UNSAFE.sub("_", ascii_name).strip("._")
    if cleaned in {"", ".", ".."}:
        return ""
    return cleaned


def allowed_file(filename: str, allowed_extensions: set[str]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_upload(
    file,
    upload_folder: Path,
    allowed_extensions: set[str],
) -> Path:
    """Save a Flask ``request.files`` entry or any object with ``filename`` and ``save``."""
    if not file or not getattr(file, "filename", None):
        raise UploadError("No file selected. Please choose an Excel file to upload.")

    if not allowed_file(file.filename, allowed_extensions):
        raise UploadError("Invalid file type. Please upload a .xlsx or .xls file.")

    filename = secure_filename(file.filename)
    if not filename:
        raise UploadError("The selected filename is not valid.")

    upload_folder.mkdir(parents=True, exist_ok=True)
    filepath = upload_folder / filename
    file.save(filepath)
    return filepath


def preview_excel(filepath: Path) -> dict:
    try:
        df = pd.read_excel(filepath)
    except Exception as exc:
        return {
            "success": False,
            "filename": filepath.name,
            "error": f"Could not read the Excel file: {exc}",
        }

    return {
        "success": True,
        "filename": filepath.name,
        "row_count": len(df),
        "columns": [str(column) for column in df.columns],
    }
