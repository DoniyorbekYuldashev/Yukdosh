"""Scraper with INCREMENTAL fetch. Each group tracks the last message id it saw; the next
run pulls only newer messages (Telegram min_id). Two execution modes:
  * PERSISTENT (scheduler): a long-lived client stays connected across cycles (efficient).
  * PER-RUN (web 'Run pipeline now'): connect, fetch, disconnect.
  * OFFLINE (no creds): read data/sample_messages.jsonl.
"""
import json
import threading
from datetime import datetime, timedelta, timezone

from .. import config

INCREMENTAL_LIMIT = 500  # safety cap on new messages pulled per group per run

_persistent = None  # a running ScraperWorker, set by the scheduler


def use_persistent(worker) -> None:
    global _persistent
    _persistent = worker


def _within(posted_at: datetime, hours_back: int) -> bool:
    if hours_back <= 0:
        return True
    return posted_at >= datetime.now(timezone.utc) - timedelta(hours=hours_back)


def _credentials_ready() -> bool:
    return bool(config.TELEGRAM_API_ID and config.TELEGRAM_API_HASH and config.TELEGRAM_PHONE)


def fetch_messages(specs: list[dict]) -> list[dict]:
    if not specs:
        return []
    if _persistent is not None:
        try:
            return _persistent.fetch(specs)
        except Exception as exc:
            print(f"[scraper] persistent fetch failed ({exc}); trying per-run")
    if _credentials_ready():
        try:
            return _fetch_real_threaded(specs)
        except Exception as exc:
            print(f"[scraper] real fetch failed ({exc}); falling back to sample data")
    return _fetch_offline(specs)


def _fetch_offline(specs: list[dict]) -> list[dict]:
    if not config.SAMPLE_DATA_PATH.exists():
        return []
    rows = []
    with open(config.SAMPLE_DATA_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    now = datetime.now(timezone.utc)
    out, per_group = [], {}
    for i, row in enumerate(rows):
        spec = specs[i % len(specs)]
        posted = now - timedelta(hours=row.get("hours_ago", i))
        if not _within(posted, spec["hours_back"]):
            continue
        link = spec["link"]
        if per_group.get(link, 0) >= spec["max_messages"]:
            continue
        per_group[link] = per_group.get(link, 0) + 1
        mid = int(row.get("id", i))
        out.append({"source_group": link, "source_msg_id": str(mid), "msg_id": mid,
                    "sender": row.get("sender", ""), "text": row["text"], "posted_at": posted})
    return out


async def collect(client, specs: list[dict]) -> list[dict]:
    """Core Telethon fetch logic, reused by both the persistent worker and per-run mode.
    `client` must already be connected/authorized."""
    out = []
    for spec in specs:
        link = spec["link"]
        last_id = spec.get("last_msg_id")
        try:
            if last_id:  # INCREMENTAL: only messages newer than last time
                kwargs = {"min_id": int(last_id), "limit": INCREMENTAL_LIMIT}
                cutoff = None
            else:        # FIRST RUN: bootstrap with the group's window
                kwargs = {"limit": spec["max_messages"]}
                hours = spec["hours_back"]
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours) if hours > 0 else None
            async for msg in client.iter_messages(link, **kwargs):
                if not msg.text:
                    continue
                posted = msg.date.replace(tzinfo=timezone.utc)
                if cutoff and posted < cutoff:
                    break
                uname = ""
                try:
                    sndr = msg.sender  # cached by iter_messages; no extra request
                    if sndr is not None and getattr(sndr, "username", None):
                        uname = "@" + sndr.username
                except Exception:
                    uname = ""
                out.append({"source_group": link, "source_msg_id": str(msg.id), "msg_id": int(msg.id),
                            "sender": uname, "text": msg.text, "posted_at": posted})
        except Exception as exc:
            print(f"[scraper] group '{link}' failed: {exc}")
    return out


def _fetch_real_threaded(specs: list[dict]) -> list[dict]:
    """Per-run: connect a fresh client in its own thread/loop, fetch, disconnect."""
    import asyncio
    box = {}

    def worker():
        try:
            box["data"] = asyncio.run(_run(specs))
        except Exception as exc:
            box["error"] = exc

    async def _run(specs):
        from telethon import TelegramClient
        client = TelegramClient("sarbon_session", int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise RuntimeError("Telegram userbot not logged in — run: py -m app.scraper.login")
        try:
            return await collect(client, specs)
        finally:
            await client.disconnect()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box.get("data", [])
