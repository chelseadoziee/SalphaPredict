import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
UPLOAD_FOLDER = BASE_DIR / "uploads"
DATA_FOLDER = BASE_DIR / "data"
REPORTS_FOLDER = BASE_DIR / "reports"
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
ALLOWED_EXTENSIONS = {"xlsx", "xls"}


def ensure_directories() -> None:
    """Create required project directories if they do not exist."""
    for folder in (UPLOAD_FOLDER, DATA_FOLDER, REPORTS_FOLDER):
        folder.mkdir(parents=True, exist_ok=True)
