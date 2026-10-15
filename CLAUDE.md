# CLAUDE.md — read this first, every session

This file is loaded automatically by Claude Code. It holds the rules and context you need
before touching anything. Deeper detail lives in:

- `docs/PRODUCT.md` — what the product is, who it's for, business model, competitors,
  naming, roadmap, and the history of every major decision (and WHY).
- `docs/TECHNICAL.md` — full technical reference: architecture, every table/setting,
  parser internals, bot flows, deployment, recipes ("how do I add X"), troubleshooting.
- `DEPLOY.md` — step-by-step production deploy: one Azure VM (Postgres + app in Docker).

---

## 1. The project in 30 seconds

**Yukdosh** (renamed from "Sarbon24" → "Sayyor" → "Yukdosh"; the Sarbon name clashed with a
competitor, see §9) is a freight load-matching service for Uzbekistan / Central Asia,
delivered as a **Telegram bot** (no app to install, no registration, phone contacts always free).

1. A **Telegram userbot** (Telethon) scrapes public freight groups where loads are posted
   as messy text (Uzbek Latin + Cyrillic, Russian, Kazakh, typos, emojis).
2. An **LLM parser** (OpenAI `gpt-4o-mini`) turns each post into structured loads
   (from, to, truck type, tons, price, phone, comment). One post can hold 1–20 loads.
3. Loads are stored in **PostgreSQL**, deduplicated across groups.
4. Drivers use the **bot** to search by route (country > region > district) and truck
   type, see the newest loads, save routes and get **push notifications**, and post loads.
5. A small **FastAPI web admin** (password-protected) manages groups, settings, users.

Long-term vision: a 3-sided marketplace — **sellers** list goods, **buyers** buy, and
**drivers** carry the goods when neither side has a truck. Today only the freight side exists.

**Owner:** Doniyor (GitHub `DoniyorbekYuldashev`, repo `Yukdosh` — renamed from `Sarbon24` →
`Sayyor` → `Yukdosh`, private, branch `main`).

---

## 2. Stack

Python 3.12 · FastAPI + Jinja2 · aiogram 3 (bot, long polling) · Telethon (userbot) ·
SQLAlchemy 2 async + asyncpg · **PostgreSQL only** · OpenAI SDK · Docker Compose ·
optional Caddy (HTTPS, only with a domain). No frontend framework.

---

## 3. How to run

### Windows dev machine (the owner's PC)
Use `py`, not `python`. `pip.exe` is blocked by Windows Application Control → always
`py -m pip install -r requirements.txt`. Local Postgres runs natively on Windows.

```powershell
py run_scraper.py   # scraper + parser engine (start once, leave running)
py run_app.py       # bot + web admin (restart freely after UI/bot changes)
py run_all.py       # all three together (simple mode)
py run_tests.py     # zero-dependency test runner — must print "PASSED 34 FAILED 0" (or more)
```
Double-click equivalents: `run_scraper.bat`, `run_app.bat`. Admin: http://127.0.0.1:8000

### Production — see DEPLOY.md
One **Azure VM `Standard_B2als_v2`** (2 vCPU / 4 GB, Central India, ~$18/mo after the $200 credit
expires on 2026-11-14) runs 4 Docker services: `db` (Postgres 16) + web, bot, scheduler.
DB mode is chosen in `.env`: `COMPOSE_PROFILES=localdb` + `POSTGRES_*` (default) **or**
`DATABASE_URL=<Supabase session pooler>` (for shrinking to the free 1 GB B2ats_v2 later).
**Live server:** `ssh -i C:\Users\doniy\.ssh\yukdosh-key.pem doniyorazure@20.207.207.239`, code in
`~/yukdosh`. Admin login is in `C:\Users\doniy\.ssh\yukdosh-admin.txt` (never in the repo).
Backups: cron 04:00 daily → `~/yukdosh/backups/*.dump` (keeps 14).
From PowerShell, write server paths literally (`/home/doniyorazure/...`) — `$HOME` inside a
double-quoted ssh command expands to the *Windows* home.
```bash
docker compose up -d --build                 # everything
bash deploy/update.sh                        # git pull + rebuild bot & web only
bash deploy/update.sh all                    # also scraper/parser
docker compose logs -f scheduler             # watch the engine
```
Admin in prod is bound to 127.0.0.1 — open via SSH tunnel:
`ssh -i C:\Users\doniy\.ssh\yukdosh-key.pem -N -L 8000:127.0.0.1:8000 doniyorazure@20.207.207.239`
→ http://localhost:8000

### Useful one-off commands (`py -m ...` on Windows, `docker compose run --rm web python -m ...` in Docker)
`app.set_provider openai` · `app.scraper.login` · `app.scraper.logout` · `app.dbview` ·
`app.dbcheck` · `app.diag` · `app.clearqueue` · `app.reprocess` · `app.export_samples`
(details in docs/TECHNICAL.md §10)

---

## 4. Repository map (what lives where)

```
app/config.py            env config (.env loader). DATABASE_URL REQUIRED, TG_SESSION, keys
app/db.py                engine, init_db(), _ensure_columns() auto-migration, default settings seed
app/models.py            tables: settings, groups, raw_messages, loads, subscriptions, bot_users,
                         post_targets, posted_loads
app/schemas.py           ParsedLoad (pydantic) — the parser's output shape
app/pipeline.py          scrape → prefilter → mask phones → parse (batched) → store → dedup → prune
app/scheduler.py         timer loop: run_pipeline() then notify_new_loads(); persistent Telegram conn
app/notify.py            push new loads to drivers whose saved routes match
app/broadcast.py         post digests of fresh loads into Telegram groups (post_targets), no repeats
app/analytics.py         record_user() on every bot update; stats for /users page
app/main.py              FastAPI admin: /, /settings, /groups/*, /run, /api/loads, /users, /health
app/web/templates/       base.html, dashboard.html, settings.html
app/bot/main.py          aiogram bot: menu, search, latest, post a load, saved routes, /lang
app/bot/i18n.py          ALL user-facing strings in uz / kk / ru; t(), variants(), get/set_lang
app/bot/formatting.py    load card rendering (HTML), 📄 Asl matn buttons (original_kb)
app/bot/clean.py         strip source hints + ad lines from original text / comments
app/bot/queries.py       search_loads (geo + truck filter + freshness), latest, insert_listing
app/bot/subscriptions.py saved routes CRUD
app/parser/prompt.py     SYSTEM_PROMPT + build_system_prompt() + user_prompt() + batch_user_prompt()
app/parser/openai_p.py   OpenAIParser (parse, parse_batch)  ← production parser
app/parser/gemini.py     GeminiParser + SHARED helpers to_loads() / split_batch() (used by all)
app/parser/local_p.py    LocalParser (Ollama/Qwen3) — experimental, NOT batched on purpose
app/parser/mock.py       offline heuristic parser (fallback) — also exports _find_price used by bot
app/parser/factory.py    get_parser(provider, ...) → openai | gemini | local | mock
app/parser/normalize.py  CITY_ALIASES, TRUCK_ALIASES, canonical_city, canonicalize_trucks (fuzzy)
app/parser/geo.py        region/district hierarchy, RU↔UZ city aliases, location_match()
app/parser/dedup.py      dedup_hash(): route + last-9-digits of phone
app/scraper/             telethon_client.py (incremental fetch), worker.py (persistent), login/logout
data/patterns.md         short domain hints injected into the prompt
data/few_shot.jsonl      6 worked examples injected into the prompt (real failure cases)
data/sample_messages.jsonl  offline demo input (used when no Telegram creds)
data/real_samples.jsonl  exported real posts for labelling (contains real phone numbers!)
tests/ + run_tests.py    geo, trucks, dedup, filters
runner.py, run_*.py      process launchers (split architecture)
deploy/                  server_setup.sh, update.sh, backup.sh
Dockerfile, docker-compose.yml, Caddyfile, .env.example, DEPLOY.md
assets/                  logo files (final: icon-truck-star.svg/png, teal #0F766E; wordmark now "Yukdosh")
Sarbon24_*.docx/pdf      research docs + Uzbek pitch deck (not code; filenames not yet renamed)
```
`sarbon.db`, `_t.db*` are old SQLite leftovers — unused, ignored by git and Docker.

---

## 5. HARD RULES (breaking these caused real bugs before)

1. **PostgreSQL only. Never add a SQLite fallback.** `config.py` raises if `DATABASE_URL`
   is missing — keep it that way. (A silent SQLite fallback once made the app run against
   the wrong DB and the owner was rightly upset.)
2. **Phone numbers must never reach an external API.** `pipeline._mask_phones()` strips them
   before `parse_batch`; `_reattach_phones()` puts the real ones back from the original text
   and must NEVER blank a phone the model returned when regex finds none. Keep both.
3. **Deleting raw_messages:** always unlink first —
   `UPDATE loads SET raw_message_id=NULL` — then delete (Postgres enforces the FK).
4. **`batch_user_prompt()` in prompt.py is imported by openai_p and gemini.** It was once
   deleted by accident and silently broke OpenAI. Don't remove it.
5. **Local parser does NOT batch** (batching made small models merge multi-load posts).
   Paid APIs DO batch (`BATCH_SIZE = 10`). Keep the circuit breaker in `run_pipeline`
   (stops the run when a whole wave fails — prevents quota-draining retry storms).
6. **Every user-facing string goes through `app/bot/i18n.py` in ALL THREE languages
   (uz, kk, ru).** Button handlers match with `F.text.in_(variants("key"))`, never a
   hard-coded string, so switching language never breaks buttons.
7. **New DB column →** add it to the model AND to `_WANTED_COLUMNS` in `db.py`
   (use `BOOLEAN DEFAULT 0`; it's converted to `FALSE` for Postgres automatically).
8. **New truck type → update 5 places:** `normalize.TRUCK_ALIASES`, `prompt.SYSTEM_PROMPT`
   truck list, `bot/main.TRUCK_CODES`, `formatting._TRUCK_KEYS`, and `tk_<code>` in i18n for
   uz/kk/ru. Then add a test in `tests/test_trucks.py` / `run_tests.py`.
9. **Don't show the poster's Telegram username on cards** (owner removed it on purpose;
   the DB column `poster_username` stays). No "manba: @group" line. What bot cards show about
   the source is the **owner's admin setting `card_source_mode`** (Settings → Bot cards):
   `original` (default — 📄 Asl matn button) | `link` (🔗 E'lon manbasi) | `both` | `none`.
   **Group posts never show either.** The **📄 Asl matn** button (`raw:<load_id>`) shows the original
   post text inside the bot, cleaned by `app/bot/clean.py`: links, @mentions, #hashtags and
   whole ad lines (other bots/channels/groups, "Admin:", "kirish:", "orqali yuborildi"…) are
   removed; card comments lose links/@mentions/#hashtags too. Calibrated on 5,675 real posts —
   "bot" only as a separate word (places end in -obot: Qo'shrabot, Bekobot), never "Telegram"
   (contact lines), and **a line with a phone number is never dropped**. Tests guard all three.
10. **No price → show "kelishiladi" / "келісіледі" / "договорная"** (key `price_none`).
11. **Secrets live only in `.env`** (never commit; `.gitignore`/`.dockerignore` cover it).
    In Docker, `TG_SESSION` is set by `docker-compose.yml`; `DATABASE_URL` is built from
    `POSTGRES_*` (local db container) unless `.env` sets it (hosted DB: Supabase **Session**
    pooler — not Direct (IPv6-only) nor Transaction (breaks asyncpg)).
    Never `docker compose down -v` on the server — it deletes the database volume.
14. **Loads are deleted after `load_retention_days`** (DB setting, default 5; 0 = keep) at the
    end of every pipeline run — keeps the DB ~15–20 MB. Back up the DB before running the
    pipeline against data you want to keep.
15. **Search/notify queries `defer(Load.raw_text)`** — cards never show it and it's most of each
    row's bytes. Don't touch `load.raw_text` on objects returned by those queries (it raises
    outside the session).
12. **Only one copy of the bot and scraper may run at a time** (same BOT_TOKEN or the same
    Telegram session in two places → conflicts / session revoked).
13. After editing any Python file: `python -m py_compile <file>` and `py run_tests.py`.
    (In the old Cowork environment edits sometimes truncated files — verify the file end.)

---

## 6. Bot UX facts the owner cares about (exact texts matter)

Main menu (uz), order is fixed:
```
[ ➕ Yuk e'lonini berish ]                     (full-width top row)
[ 🔍 Yuk qidirish ] [ 🔔 Yo'nalishlarim ]       (search LEFT, routes RIGHT — owner's choice)
[ 🆕 Yangi yuklar ] [ ℹ️ Yordam ]
```
(see `menu_kb()` in bot/main.py)
Search = ask origin → destination ('-' = any) → optional truck type (inline buttons) →
paged results (5 per page, "Keyingi ➡️"). Region names match all their districts
("Qashqadaryo" finds Kitob, Qarshi…), country matches everything in it, RU/UZ spellings
match (Бухара = Buxoro). Only loads newer than `load_active_hours` (default **12h** — owner raised it from 6h on
2026-10-05 because quiet routes had too few loads) are shown, newest first.
Card shows: route, trucks ×count, tons, cargo, price, phone, comment, time (Tashkent UTC+5,
"Bugun 16:54"). Multi-card messages (search pages, "Yangi yuklar") number the cards and carry
`📄 1 … 📄 N` buttons + a hint line; a single card (notifications) gets one `📄 Asl matn` button.
Bot-posted loads have no button (no original post).

**Group posting** (admin → Settings → "Groups to post loads to", added 2026-10-16): per group —
@username/chat id, every N minutes, loads per post (1–10), from/to filter (geo hierarchy, empty =
any), truck type, language. Same card (unnumbered, no buttons), header
"🆕 latest_title", footer `group_post_footer` → @bot. Never reposts a load to the same group.
Runs from the scheduler tick (so only while the scheduler is on). The bot must be a member allowed
to post (admin in channels); send errors show under the group in the admin.

---

## 7. Parser facts

- Production provider: **openai / gpt-4o-mini**, set in DB setting `parser_provider`
  (fresh DB seeds `gemini` → run `app.set_provider openai` after deploy).
- Prompt = `SYSTEM_PROMPT` + `data/patterns.md` + `data/few_shot.jsonl`. Output is lean
  JSON (`{"loads":[...]}`, empty fields omitted). Rule #1 of the prompt: split EVERY direction
  into its own load.
- To improve accuracy: add a real failing post + correct output to `few_shot.jsonl`
  (keep it small — ~6 examples; every example costs tokens on every call).
- OpenAI data-sharing free tier is ON for the project: 2.5M tokens/day free on mini models
  (tier 1–2). Phone masking is what makes sharing acceptable. Watch the Usage page.
- Local Qwen3 (Ollama) was tried and rejected for production — too many mistakes on
  multi-load Uzbek/Russian posts even at 14B. Code kept for experiments.

---

## 8. How to work with the owner (important)

- Doniyor is building this mostly alone and is **not a deep terminal/DevOps expert**.
  Give exact, copy-pasteable commands, say WHERE to run them (Windows PowerShell vs server
  SSH), and what the expected output looks like.
- When he asks for **options/methods, present them first and WAIT** for his choice
  ("do not implement yet" means exactly that). When he says "implement it", do it fully.
- He wants **honest, critical answers**, not agreement. Say when an idea is weak and why.
- Keep answers **concise**. He often writes in English with typos; bot copy is Uzbek first,
  then Kazakh and Russian.
- He tests against **real Telegram posts** and reports concrete failures — fix the root
  cause and add the case to few-shot/tests.
- Never silently change behaviour he explicitly set (menu order, texts, removed fields).

---

## 9. Current status & open items (update this section as things change)

- ✅ Pipeline, bot (uz/kk/ru), saved routes + notifications, admin, analytics, phone masking,
  token savings (batching, compressed prompt), split processes, Docker/Oracle deploy files.
- ✅ **Deployed 2026-10-15** on Azure VM `yukdosh-server` (B2als_v2, Central India, Ubuntu 24.04,
  Docker 29, Postgres 16 container). PC data (6 groups, 7 bot users, settings) restored; Telegram
  session copied (no re-login); queue cleared with `app.clearqueue`. First run: +222 loads from
  244 msgs in 11 OpenAI calls; old August loads pruned; DB 15 MB. GitHub deploy key (read-only)
  "yukdosh-server (Azure)". **The PC copy must stay stopped** (same bot token + session).
  ⏳ **Upgrade the Azure account to pay-as-you-go before 2026-11-14** (credit expiry), then
  ~$20–28/mo. ⏳ $5 budget alert. Rejected hosting options: see docs/PRODUCT.md #19–20.
- ✅ Phones re-attached live: 187 of the first 222 loads carry a phone (the rest had none).
  ⏳ Check daily OpenAI token usage vs the 2.5M free limit.
- ✅ **Renamed to Yukdosh** (owner's choice, 2026-10-03; previously Sarbon24 → Sayyor on
  2026-09-28. "Sarbon" clashed with a competitor, IT GENIUS MCHJ, same niche). Code-level rename
  done: i18n texts (uz/kk/ru), web admin titles, logo wordmark, README/docs, Docker/infra
  identifiers (DB name/user `yukdosh`, TG_SESSION `yukdosh_session`, image name, linux user),
  GitHub repo renamed to `Yukdosh`, local git remote updated.
  ✅ New bot **@yukdoshbot** (token swapped on server + PC 2026-10-15; @yukdosh_bot was taken).
  Old @sarbon24_bot no longer runs. ⏳ BotFather: display name/description/userpic/commands
  for @yukdoshbot; redirect note on @sarbon24_bot. ⏳ Domain/trademark checks (cctld.uz,
  ima.uz); pitch deck / research `.docx`/`.pdf` files still say Sarbon24.
- ⏳ Admin "Run pipeline now" button can't scrape inside Docker (session lives only in the
  scheduler container) — scraping happens via the scheduler; fine for now.
- ⏳ `app/parser/groq.py` is dead code (factory doesn't route "groq").
- 🔜 Roadmap: shippers post loads directly (2-sided), ratings/trust, in-app deal records +
  documents, goods marketplace (sellers → buyers → drivers), paid features. See docs/PRODUCT.md.
