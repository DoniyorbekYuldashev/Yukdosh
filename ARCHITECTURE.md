# Sarbon24 — Architecture & Process (definitive)

A freight load-matching service for Central Asia. It reads messy load posts from Telegram
groups, uses an LLM to turn them into clean structured loads, stores them, and serves matched
loads to truck drivers through a Telegram bot.

---

## 1. The core process (end to end)

```
Telegram groups
      │  (userbot / Telethon, INCREMENTAL: only new messages since last time)
      ▼
 raw_messages  ── stored verbatim in DB (full text, group, message id, time)
      │
      │  (LLM parser: Gemini / Groq / OpenAI — swappable; runs 5 in parallel)
      ▼
 parse → validate → normalize cities → split multi-load → drop junk → dedup
      │
      ▼
   loads  ── structured rows in DB (From, To, truck type/count, cargo, weight,
      │       price, phone, comment, post link, timestamps)
      │
      ├──► Web dashboard (admin: view, settings, run)
      └──► Telegram bot ──► driver searches by city ──► matched loads from DB
                        └─► (Milestone 3) driver saves a route ──► push notifications
```

**Yes — every message is persisted twice:** the raw post in `raw_messages`, and each parsed
load in `loads`. The bot always serves *from the database*, never by scraping live.

---

## 2. Why this architecture (the decision)

We evaluated two models:

| | On-demand (scrape+parse per driver query) | **Scheduled → store → serve (chosen)** |
|---|---|---|
| LLM cost | re-parses same posts for every driver 💸 | parse **once**, serve unlimited times |
| Driver speed | waits seconds for scrape+LLM | instant DB query |
| Telegram ban risk | hammered on every search | controlled, once per interval |
| Complexity | live scrape+parse+match in one request | clean separation |

**Conclusion: keep the current architecture.** It is the correct, standard design for this
problem (the same pattern Numeo/ATI-style load boards use). We refine parts (model, prompts,
labels), we do **not** rebuild. The pieces that make it right:

- **Separation of ingest and serve** — scraping/parsing is one job; answering drivers is another.
- **Swappable parser** — the LLM is behind one interface, so switching Gemini↔Groq↔OpenAI is a
  dropdown, never a code change. This is what lets us chase accuracy cheaply.
- **Incremental scraping** — a per-group cursor (`last_msg_id`) means each run pulls only new
  posts, so busy groups are captured fully and cheaply.
- **Freshness window** — loads expire from the driver view after N hours, so drivers only see
  live loads without deleting history.

---

## 3. Components

| Piece | File | Responsibility |
|---|---|---|
| Scraper (userbot) | `app/scraper/telethon_client.py`, `worker.py` | Pull new messages per group (incremental); persistent connection in the scheduler |
| Parser (swappable) | `app/parser/` (`base`, `mock`, `groq`, `gemini`, `factory`, `prompt`, `normalize`, `dedup`) | Turn text → structured loads; multi-load split; comment catch-all; city normalization; dedup |
| Pipeline | `app/pipeline.py` | Orchestrates scrape → parse (parallel) → filter → dedup → store |
| Scheduler | `app/scheduler.py` | Runs the pipeline on a timer (on/off + interval from Settings) |
| Web admin | `app/main.py`, `app/web/templates/` | Dashboard + dynamic Settings (groups, windows, provider, model, scheduler) |
| Bot | `app/bot/` (`main`, `queries`, `formatting`) | Driver search + posting; renders load cards; (M3) notifications |
| DB | `app/models.py`, `app/db.py` | SQLAlchemy models + auto-migration; SQLite (dev) / Postgres (prod) |

Three long-running processes + a database: **web**, **bot**, **scheduler**, **Postgres** —
orchestrated by `docker-compose.yml`.

---

## 4. Data model (key tables)

- **groups** — group link, enabled, per-group window overrides, `last_msg_id` cursor.
- **raw_messages** — source group, message id, sender, full text, time, processed flag.
- **loads** — is_load, listing_type, From/To (+regions), cargo_type, weight, truck_type,
  truck_count, price+currency, phone, comment, language, **source_msg_id (+ post link)**,
  dedup_hash, timestamps.
- **settings** — everything tunable at runtime (scrape window, provider, model, scheduler, keys).

---

## 5. Model strategy (the real accuracy lever)

The architecture is model-agnostic; accuracy is a *model + examples* problem:

- **Gemini Flash (free)** — strong multilingual, 1,500 req/day, 1M tokens/min → best free fit for
  our volume. **Current recommendation.**
- **Groq (free)** — fast; 70B is good but rate-limited on the free tier (caused "parse failed").
- **OpenAI gpt-4o-mini (paid, ~$0.30 to parse ~800 msgs)** — most reliable; worth $5 if we want
  maximum quality. Trivial to add (same swappable interface).
- **Few-shot labels** (`data/few_shot.jsonl`) + **patterns** (`data/patterns.md`) improve any
  model at inference time. This growing labeled set is also the asset for future fine-tuning.

**Plan:** run Gemini now; keep OpenAI as the paid fallback; keep labeling. No fine-tuning yet.

---

## 6. Deployment

- **Dev:** SQLite + three `py -m` processes locally.
- **Prod:** `docker compose up -d` → Postgres + web + bot + scheduler. Secrets in `.env`;
  behavior in the Settings UI; the Telegram session file is mounted into the scheduler.
- Next: put it on a small VPS so it runs 24/7; add restart policies + logs.

---

## 7. Roadmap

1. **Now:** lock the parser model (Gemini), finish labeling, verify quality on real loads. ← here
2. **Milestone 3:** driver **saved routes** + **push notifications** (bot pings a driver when a
   matching load appears). The daily-use hook.
3. **Deploy:** Docker + Postgres on a VPS, 24/7.
4. **Later:** goods marketplace (buyer↔seller), broker tools, monetization.

---

## 8. Honest assessment

The architecture is sound and does **not** need a big rewrite — that would waste effort. The
gaps you feel are (a) parsing accuracy, fixed by a better model (Gemini/OpenAI) + more labels,
and (b) clarity, fixed by this document. We refine, we don't restart. The next real feature work
is Milestone 3, then deployment.
