# Yukdosh

Freight load-matching for Uzbekistan / Central Asia inside Telegram: a userbot collects load
posts from public Telegram groups, an LLM (OpenAI gpt-4o-mini) turns messy uz/ru/kk text into
structured loads, and drivers search, save routes and get notified through a Telegram bot.
A small password-protected web admin manages groups and settings.

**Read these, in order:**

1. [`CLAUDE.md`](CLAUDE.md) — rules, commands, repo map, current status (start here)
2. [`docs/PRODUCT.md`](docs/PRODUCT.md) — product, business model, competitors, naming, decision history
3. [`docs/TECHNICAL.md`](docs/TECHNICAL.md) — full technical reference, recipes, troubleshooting
4. [`DEPLOY.md`](DEPLOY.md) — production deploy on Oracle Cloud Always Free with Docker

Quick start (Windows dev): fill `.env` (see `.env.example`, `DATABASE_URL` required), then
`py -m pip install -r requirements.txt`, `py run_all.py`, open http://127.0.0.1:8000.
Tests: `py run_tests.py`.
