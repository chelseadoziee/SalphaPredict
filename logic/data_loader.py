from pathlib import Path

import pandas as pd
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class UploadError(Exception):
    """Raised when an uploaded file fails validation or cannot be saved."""


def allowed_file(filename: str, allowed_extensions: set[str]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_upload(
    file: FileStorage,
    upload_folder: Path,
    allowed_extensions: set[str],
) -> Path:
    if not file or not file.filename:
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
