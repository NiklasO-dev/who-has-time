import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DEV_SECRET_KEYS = frozenset(
    {
        "dev-change-me-in-production",
        "dev-local-secret-change-me",
    }
)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'who_has_time.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "").rstrip("/")
    GIT_REPO_URL = "https://github.com/NiklasO-dev/who-has-time"
    MAX_POLL_DAYS = int(os.environ.get("MAX_POLL_DAYS", "14"))
    ALLOWED_SLOT_MINUTES = (15, 30, 60)
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1").lower() in ("1", "true", "yes")


def is_dev_mode() -> bool:
    if os.environ.get("WHT_ALLOW_DEV_SECRET", "").lower() in ("1", "true", "yes"):
        return True
    return os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")


def validate_secret_key(secret_key: str) -> None:
    if is_dev_mode():
        return
    if not secret_key or secret_key in DEV_SECRET_KEYS:
        raise RuntimeError(
            "SECRET_KEY must be set to a strong random value in production. "
            "Set WHT_ALLOW_DEV_SECRET=1 only for local development."
        )
