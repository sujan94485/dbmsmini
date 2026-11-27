import os
from dotenv import load_dotenv

# Load environment variables from a local .env file when present (no-op on Vercel)
load_dotenv()


def _int_env(name: str, default: int) -> int:
    """Safely parse an integer environment variable with a fallback default."""
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    """Application configuration loaded strictly from environment variables."""

    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"

    # MySQL Database Settings (configured via .env locally or Vercel Environment Variables)
    DB_HOST = os.environ.get("DB_HOST", "")
    DB_PORT = _int_env("DB_PORT", 3306)
    DB_USER = os.environ.get("DB_USER", "")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "")
    DB_SSL_MODE = os.environ.get("DB_SSL_MODE", "")
    DB_SSL_CA = os.environ.get("DB_SSL_CA", "")

    # Read-Only MySQL User & Execution Limits (Phase 4)
    DB_READONLY_USER = os.environ.get("DB_READONLY_USER", "")
    DB_READONLY_PASSWORD = os.environ.get("DB_READONLY_PASSWORD", "")
    MAX_QUERY_ROWS = _int_env("MAX_QUERY_ROWS", 200)
    QUERY_TIMEOUT_MS = _int_env("QUERY_TIMEOUT_MS", 5000)

    # Dedicated MySQL User for Query History (Phase 5)
    DB_HISTORY_USER = os.environ.get("DB_HISTORY_USER", "")
    DB_HISTORY_PASSWORD = os.environ.get("DB_HISTORY_PASSWORD", "")

    # Gemini AI Settings
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
