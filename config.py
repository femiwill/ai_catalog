import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
if DATA_DIR.exists() and DATA_DIR.is_dir():
    DB_PATH = DATA_DIR / "ai_atlas.db"
else:
    DB_PATH = BASE_DIR / "ai_atlas.db"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-prod")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DB_PATH}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "atlas-admin-2026")
    SITE_NAME = "AI Atlas"
    SITE_TAGLINE = "The executive map of the AI landscape"
