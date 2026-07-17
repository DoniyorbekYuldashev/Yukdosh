# Sarbon24 — freight & goods marketplace for Central Asia

*Named for the **sarbon** — the caravan leader who guided trade caravans to their destination.*

Sarbon24 connects the three sides of trade in one place: **sellers/load owners** who
have goods or cargo, **buyers**, and **truck drivers** who move it. It scrapes freight
posts from Telegram groups, uses a swappable LLM (Groq) to turn messy multilingual
text into clean structured listings, and serves everyone through a Telegram bot.

Everything runs **offline out of the box** (bundled sample posts + an offline `mock`
parser), so you can try the whole flow before adding any keys.

## Run everything with Docker (recommended — Postgres + all services)

One command starts Postgres, the web admin, the driver bot, and the auto-scraper:

```bash
# 1) fill .env with BOT_TOKEN, GROQ_API_KEY, TELEGRAM_API_ID/HASH/PHONE
# 2) log in the Telegram userbot ONCE (creates sarbon_session.session, mounted into the scheduler):
py -m app.scraper.login
# 3) launch the whole stack:
docker compose up -d --build
```

Services (see `docker-compose.yml`):
- **db** — PostgreSQL (data persisted in the `pgdata` volume)
- **web** — admin UI at http://localhost:8000
- **bot** — the Telegram driver bot
- **scheduler** — auto-scraper with a persistent Telegram connection

Turn the scheduler on and set the interval in **Settings → Auto-scrape scheduler**.
Logs: `docker compose logs -f scheduler`.  Stop: `docker compose down`.

Secrets live in `.env`; day-to-day behavior (scheduler on/off, interval, groups, provider,
freshness window) lives in the Settings UI. The DB URL is set to Postgres by compose.

---

## 1. Web app + pipeline (admin)

```bash
cd sarbon
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 → **Run pipeline now**. The **Settings** page is fully dynamic:
Telegram groups to scrape, the scrape window (latest N messages / last N days / dedup
window), and the parser model (`mock` offline, `gemini`, or `groq`) with the API key.

## 2. Telegram bot — two-sided (drivers + sellers)

Get a token from **@BotFather**, put it in `.env` as `BOT_TOKEN`, then:

```bash
python -m app.bot.main
```

**Search side** (drivers/buyers): 🔍 search loads by route, 🆕 newest loads,
🛒 goods for sale, 🚛 empty trucks — each shown as a clean card.

**Post side** (load owners/sellers): ➕ **E'lon berish** runs a short guided Q&A to
post one of three listing types:

- 📦 **Yuk bor** — cargo that needs transport (from → to, cargo, weight, price, phone)
- 🛒 **Mahsulot sotaman** — goods for sale (product, location, quantity, price, phone)
- 🚛 **Bo'sh mashinam bor** — an empty truck looking for a load

First-party posts are saved to the same database and appear instantly in search —
so the bot both *aggregates* scraped loads and *collects* fresh ones directly.

## 3. Turning on Groq (real parsing)

Free key at https://console.groq.com/keys → Settings → provider **groq**, paste key,
Save. Messy posts (`Тошкент-Москва фура керак, 20 тонна, тент, 45 млн`) become
structured listings. No key? It safely falls back to `mock`.

## 4. Real Telegram scraping

`pip install telethon`, fill `TELEGRAM_API_ID/HASH/PHONE` in `.env` (from
https://my.telegram.org). Without credentials the scraper reads `data/sample_messages.jsonl`.

## How it fits together

```
Telegram groups ─(scraper: Telethon OR offline sample)→ raw_messages
   ─(parser: groq / gemini / mock)→ normalize → dedup → listings (DB)
        ├── web dashboard  (view / manage)
        └── Telegram bot   ── search loads / goods / trucks
                           └─ post loads / goods / trucks  → same DB
```

| Piece | Location |
|---|---|
| Dynamic config + models (listings) | `app/models.py` |
| Scraper (real + offline) | `app/scraper/telethon_client.py` |
| Swappable parser | `app/parser/` (`base`, `mock`, `gemini`, `groq`, `factory`) |
| Normalization / dedup | `app/parser/normalize.py`, `app/parser/dedup.py` |
| Pipeline | `app/pipeline.py` |
| Web UI + API | `app/main.py`, `app/web/templates/` |
| Bot (search + posting) | `app/bot/` (`main`, `queries`, `formatting`) |

## Roadmap
- **Done:** scraping + parsing pipeline, dynamic admin, two-sided bot (search + post).
- **Next:** saved-route subscriptions + push notifications; buyer↔seller deal flow that
  auto-creates a transport load; matching engine; then B2B tools for logistics companies.
