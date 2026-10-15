"""Run EVERYTHING together (web + bot + scraper) with one command:

    py run_all.py

For day-to-day work prefer the SPLIT, so UI changes don't interrupt scraping:
    py run_scraper.py    (engine — start once, leave running)
    py run_app.py        (bot + web — restart freely for UI changes)
"""
from runner import run, WEB, BOT, SCHEDULER

if __name__ == "__main__":
    run([WEB, BOT, SCHEDULER], banner="✅ All started.  Admin: http://127.0.0.1:8000")
