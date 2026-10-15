"""UI — the driver bot + the web admin panel.

    py run_app.py

Restart THIS freely whenever you change formatting / menu / text / language — it's stateless
(reads from the database). The scraper (run_scraper.py) keeps running untouched, so your
Telegram connection and in-flight parsing are never interrupted.
"""
from runner import run, WEB, BOT

if __name__ == "__main__":
    run([WEB, BOT], banner="✅ Bot + Web running.  Admin: http://127.0.0.1:8000")
