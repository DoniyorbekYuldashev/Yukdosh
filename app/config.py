"""Environment-level config. Anything a user tweaks day-to-day lives in the DB
Settings table (editable from the UI) instead of here."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# Load a .env file if present (tiny loader, no extra dependency).
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        k, _, v = _line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


DATABASE_URL = _env("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'sarbon.db'}")

# Telegram userbot credentials (optional; enables real scraping)
TELEGRAM_API_ID = _env("TELEGRAM_API_ID")
TELEGRAM_API_HASH = _env("TELEGRAM_API_HASH")
TELEGRAM_PHONE = _env("TELEGRAM_PHONE")

# Driver-facing bot token from @BotFather
BOT_TOKEN = _env("BOT_TOKEN")

# Gemini key — used as a fallback if not set in the web Settings UI.
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.0-flash")
OPENAI_API_KEY = _env("OPENAI_API_KEY")

# Web admin login. If ADMIN_PASSWORD is empty, auth is OFF (local dev only) — ALWAYS
# set a strong ADMIN_PASSWORD in production so the settings/keys page is protected.
ADMIN_USER = _env("ADMIN_USER", "admin")
ADMIN_PASSWORD = _env("ADMIN_PASSWORD")

SAMPLE_DATA_PATH = BASE_DIR / "data" / "sample_messages.jsonl"
