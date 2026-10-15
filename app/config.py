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


DATABASE_URL = _env("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Yukdosh runs on PostgreSQL — put it in .env, e.g.\n"
        "  DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/yukdosh"
    )
# Railway / Heroku / most managed Postgres give a plain 'postgres://' or 'postgresql://'
# URL, but our async SQLAlchemy needs the asyncpg driver. Upgrade it automatically so you
# can paste the provider's URL as-is.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+asyncpg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+asyncpg://" + DATABASE_URL[len("postgresql://"):]

# Telegram userbot credentials (optional; enables real scraping)
TELEGRAM_API_ID = _env("TELEGRAM_API_ID")
TELEGRAM_API_HASH = _env("TELEGRAM_API_HASH")
# Where the userbot session file lives (without ".session"). Docker points this at a volume.
TG_SESSION = _env("TG_SESSION", "yukdosh_session")
TELEGRAM_PHONE = _env("TELEGRAM_PHONE")

# Driver-facing bot token from @BotFather
BOT_TOKEN = _env("BOT_TOKEN")

# Gemini key — used as a fallback if not set in the web Settings UI.
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.0-flash")
OPENAI_API_KEY = _env("OPENAI_API_KEY")

# Local model (Ollama / LM Studio / vLLM) — free, runs on your GPU.
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://localhost:11434/v1")
LOCAL_MODEL = _env("LOCAL_MODEL", "qwen3:8b")

# Web admin login. If ADMIN_PASSWORD is empty, auth is OFF (local dev only) — ALWAYS
# set a strong ADMIN_PASSWORD in production so the settings/keys page is protected.
ADMIN_USER = _env("ADMIN_USER", "admin")
ADMIN_PASSWORD = _env("ADMIN_PASSWORD")

SAMPLE_DATA_PATH = BASE_DIR / "data" / "sample_messages.jsonl"
