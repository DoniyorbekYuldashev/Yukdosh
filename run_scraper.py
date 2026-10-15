"""ENGINE — the auto-scraper + AI parser + notifier.

    py run_scraper.py

Start this ONCE and leave it running for days — it holds the persistent Telegram connection
and continuously scrapes -> parses -> stores -> notifies. You do NOT need to restart it when
you change the bot UI / formatting / text; those live in run_app.py.
"""
from runner import run, SCHEDULER

if __name__ == "__main__":
    run([SCHEDULER], banner="✅ Scraper engine running (scrape -> parse -> store -> notify).")
