# Technical reference

Complete reference for the codebase. Start with `CLAUDE.md` (rules), then use this file to
look things up. If code and this document disagree, the code wins — then fix this document.

Contents: 1 Architecture · 2 Pipeline step by step · 3 Database · 4 Settings (DB) ·
5 Environment (.env) · 6 Parser · 7 Normalisation, geo, dedup · 8 Bot · 9 Web admin ·
10 CLI scripts · 11 Deployment · 12 Testing · 13 Recipes · 14 Troubleshooting ·
15 Known issues / tech debt · 16 Costs & limits

---

## 1. Architecture

```
 Telegram freight groups
        │  Telethon userbot (logged-in personal account), INCREMENTAL via min_id cursor
        ▼
 [scheduler process] ── app/scheduler.py ── every N min (settings) ──┐
        │ run_pipeline()                                            │ notify_new_loads()
        ▼                                                           ▼
 raw_messages ─► prefilter ─► mask phones ─► OpenAI (5 msgs/call) ─► re-attach phones
        ─► fill truck from text ─► require origin+destination ─► dedup (24h) ─► loads
                                                                   │
        ┌──────────────────────────────────────────────────────────┤
        ▼                                                          ▼
 [bot process] app/bot/main.py                       [web process] app/main.py
 search / latest / post / saved routes / /lang       admin: dashboard, settings, groups,
 (reads + writes Postgres, long polling)             users, run pipeline, /health
        └──────────────────────── PostgreSQL ─────────────────────┘
```

Three independent processes share one Postgres database and never call each other:

| Process | Entry | Stateful? | Restart when |
|---|---|---|---|
| **scheduler** (engine) | `python -m app.scheduler` | yes — live Telegram connection (session file) | parser/pipeline/scraper changes |
| **bot** | `python -m app.bot.main` | no (FSM state in memory only) | bot texts/flows/formatting |
| **web** | `uvicorn app.main:app` | no | admin UI changes |

Dev launchers (`runner.py`): `run_scraper.py` = scheduler; `run_app.py` = web + bot;
`run_all.py` = all three. In Docker each is a separate service.

Design principle: **ingest once, serve many.** The LLM parses each post once; drivers are
served from the DB instantly. The LLM sits behind one interface (`LLMParser`), so the
provider is a setting, not a code change.

---

## 2. Pipeline step by step (`app/pipeline.py::run_pipeline`)

Constants: `DEDUP_WINDOW_HOURS=24`, `PARSE_CONCURRENCY=5`, `MAX_PARSE_PER_RUN=200`,
`BATCH_SIZE=5`, `BATCH_CHARS=3000`. Retention comes from the `load_retention_days` setting (§4).

1. **Load settings** from the `settings` table (fresh every run).
   Provider = `parser_provider`; keys = setting value or `.env` fallback.
2. **Build specs** for every enabled group: `max_messages`/`hours_back` (group override or
   global), `last_msg_id` cursor.
3. **Fetch** (`scraper/telethon_client.fetch_messages`):
   persistent worker (scheduler) → per-run client (web button) → offline sample file.
   First run of a group: latest `max_messages` within `hours_back`. After that: only
   messages with id > `last_msg_id` (cap 500 per group per run). Captures sender @username.
4. **Store raw** messages not seen before (unique by group + message id); advance
   `groups.last_msg_id`.
5. **Select queue:** up to 200 newest unprocessed raw messages.
6. **Prefilter (no API cost):**
   - `_looks_like_junk` — fewer than 4 letters/digits after stripping links/mentions/emoji.
   - `_looks_like_load` — must contain a phone, a truck word, a tonnage (`20t`, `кг`, `куб`),
     or a known place. Otherwise marked processed and skipped.
   - Byte-identical reposts (same letters/digits) → parse only one representative.
   - **Cross-run reposts:** `raw_messages.text_hash` (md5 of letters+digits) — if the same hash
     was already processed in the last 24h, skip the API (its loads exist). Measured 2026-10-16:
     63% of load posts are exact reposts within 24h. Logged as "N already parsed in 24h".
7. **Mask phones** (`_mask_phones`): every digit run (never across a line break) that
   `_phone_at()` calls a phone is replaced by a space. A phone = 9–13 digits; `+…` always;
   NOT a phone when a currency follows on the same line ("3 900 000 сум", "4800$", "млн"), a price
   word precedes it on the same line ("Narx:", "Фрахт", "Ставка", "Аванс", "$"), or it is grouped in
   thousands ending 000 ("12 500 000") without a 998/7/8 prefix. Prices, tons, dates stay visible.
   Before 2026-10-16 any 7+ digit run was a "phone": prices, dates (`22 07 2026`) and volumes
   (`86-88-92-96`) were shown as phones and the real number was cut (only 2 kept).
8. **Parse in batches:** up to 5 messages / 3,000 chars per call → `parser.parse_batch`
   (temperature 0, max 6,000 output tokens; broken JSON → retry those messages one by one;
   the batch prompt states the exact count — without it the model kept adding `{"i":N,"loads":[]}`
   up to the token limit; a single message uses the plain `user_prompt` format),
   2 chunks per wave,
   run in a thread executor. **Circuit breaker:** if every item of a wave errors, stop the run
   (prints "API QUOTA EXHAUSTED" for quota errors).
9. **Per message result:**
   - error with `429`/`rate_limit`/`quota` → left unprocessed (retried next run);
   - other error → `parse_attempts += 1`, give up after 3;
   - success → `_reattach_phones` (real phones from the ORIGINAL text, max 2, deduped by last
     9 digits; if regex finds none, the model's value is kept only if it has ≥7 digits — the
     model writes words like "СРОЧНО" there), `_fill_truck_from_text` (single load: whole
     text; several loads: only if none has a truck and all truck lines agree — one shared
     "🚛 Тент ёки Реф фура керак" line; plain "fura" = tent, "ref fura" = ref),
     `_fill_cargo_header` (one "Napitka 👇" header followed by a route line → cargo of all loads), `_check_dates` (drop a model 'ready'/'today'/'tomorrow' the post doesn't say; add
     'ready' for "груз готов"/"ortishga tayyor"), `_clean_comments` (drop "kelishiladi",
     WhatsApp/Telegram/IMO, and "Аванс…" when `advance` is set), keep only loads having BOTH
     origin and destination.
10. **Dedup & insert:** `dedup_hash(load)`; if the same hash exists with `posted_at` in the
    last 24h → skip; else insert `Load` (copies raw text, source group/msg id, sender).
11. **Prune** (skipped when `load_retention_days` = 0): loads with `posted_at` older than
    `load_retention_days` (default 5) are deleted, then processed raw messages older than that —
    after `UPDATE loads SET raw_message_id = NULL` for them (FK!). Keeps the DB ~15–20 MB.
12. Returns stats (`loads_created`, `api_calls`, `prefiltered_junk`, `duplicate_texts_skipped`,
    `rate_limited`, `api_error`, …) which the scheduler prints; then the scheduler calls
    `notify_new_loads(bot)`.

---

## 3. Database (`app/models.py`) — PostgreSQL

Tables are created by `Base.metadata.create_all` at startup (`init_db`, retried 20× so services
can start before Postgres is ready). New columns on existing tables are added by
`_ensure_columns()` from `_WANTED_COLUMNS` (no Alembic).

**settings** — `key` (PK, str 64), `value` (text). See §4.

**groups** — `id`, `link` (unique, e.g. `https://t.me/xxx`), `title`, `enabled`,
`max_messages`, `hours_back` (per-group overrides, null = global), `last_msg_id` (cursor),
`created_at`. First startup seeds one example group.

**raw_messages** — `id`, `source_group`, `source_msg_id`, `sender` (@username or ""),
`text`, `posted_at`, `processed`, `parse_attempts`.

**loads** — one row per extracted load / bot post:
- `is_load` (False = empty truck), `listing_type` (`load` | `goods` | `truck`)
- `origin_city`, `origin_region`, `destination_city`, `destination_region`
- `cargo_type`, `weight_tons`, `volume_m3`, `truck_type` (comma list of codes), `truck_count`
- `price_amount`, `price_currency` (UZS/USD/RUB/KZT/EUR), `advance` ("1000 USD" | "30%" | "yes"),
  `loading_date` ("17.10" | "28-30.07" | `ready` | `today` | `tomorrow` | short text; keywords
  are shown in the reader's language, today/tomorrow counted from `posted_at`)
- `contact_phone` (comma list), `contact_name`, `comment` (everything else)
- `language_detected`, `parser_provider` (`openai`/`bot`/…), `dedup_hash` (indexed)
- `notified` (already pushed to subscribers)
- `source_group` (group link or `bot`), `source_msg_id`, `posted_by_tg` (bot poster id),
  `poster_username` (stored, NOT displayed), `raw_text`, `posted_at`, `created_at`
- `raw_message_id` → FK `raw_messages.id` (nullable)

**subscriptions** — saved routes: `tg_user_id`, `origin`, `destination` ("" = any),
`truck_type` (currently always "" — the bot doesn't ask), `active`, `created_at`.

**bot_users** — `tg_user_id` (PK), `username`, `first_name`, `language` (Telegram's),
`lang` (chosen in bot: uz/kk/ru/en), `actions` (count), `first_seen`, `last_seen`.

**post_targets** — groups/channels the bot posts into (`app/broadcast.py`): `chat` (unique,
`@username` or numeric id; `normalize_chat()` turns t.me links into `@name`), `title`,
`enabled`, `interval_minutes`, `loads_per_post` (1–10), `origin`/`destination` (geo-hierarchy
filter, "" = any), `truck_type`, `lang` (uz/kk/ru/en), `last_posted_at`, `last_error`.

**posted_loads** — `target_id`, `load_id`, `posted_at`: which load went to which target (never
repost). Plain ids, **no FKs** (loads are deleted by retention); pruned with the same retention.

Group posting flow: each scheduler tick (after `notify_new_loads`) → `post_to_groups(bot)`: for
every enabled target whose interval has passed, pick the newest active loads (load_active_hours)
matching its filter and not yet in `posted_loads`, render with `format_load(..., source=False)`
(no 🔗 link), header `latest_title`, footer `group_post_footer` (bot @username from `get_me()`),
cut to fit 4,000 chars, send with link previews off. Nothing new → no post. Send error (bot not
in group / no rights) → stored in `last_error`, retried next interval. Card fields are
HTML-escaped (`&`, `<` in posts used to break Telegram's HTML parsing).

---

## 4. Runtime settings (DB table `settings`, edited in admin → Settings)

| Key | Default seed | Meaning |
|---|---|---|
| `parser_provider` | `gemini` ⚠ | `openai` in production. `mock` / `gemini` / `openai` in the UI dropdown; `local` only via `app.set_provider local` |
| `openai_api_key` / `gemini_api_key` | "" | Optional; `.env` value used when empty |
| `scrape_max_messages` | 50 | First-run messages per group |
| `scrape_hours_back` | 24 | First-run time window (hours) |
| `scheduler_enabled` | false | Engine does nothing until this is ON |
| `scheduler_interval_minutes` | 10 | Minutes between runs (owner used 1–2 min at times) |
| `load_active_hours` | 12 | Loads older than this are hidden from search/latest/notifications (0 = never hide). Was 6 until 2026-10-05 |
| `load_retention_days` | 5 | Loads + processed raw messages older than this are deleted each pipeline run (0 = keep all) |
| `card_source_mode` | original | Bot cards (private chats only): `original` 📄 Asl matn button · `link` 🔗 E'lon manbasi · `both` · `none`. Read via `queries.card_options()` (30 s cache). Group posts never show either |

⚠ Saving the Settings form writes ALL these keys (including the provider dropdown and the
key fields). If the provider is `local`, saving the form changes it — the dropdown has no
`local` option.

---

## 5. Environment (`.env`, loaded by `app/config.py`; template `.env.example`)

| Var | Required | Notes |
|---|---|---|
| `DATABASE_URL` | **yes** (dev) | Dev: `postgresql+asyncpg://user:pass@localhost:5432/yukdosh`. Docker: built by compose from `POSTGRES_*` unless set here — set it only for a hosted DB (Supabase **Session pooler** URI; Direct is IPv6-only, Transaction mode breaks asyncpg). `postgres://` / `postgresql://` are auto-upgraded. URL-encode special chars in the password (`@`→`%40`, `#`→`%23`). |
| `COMPOSE_PROFILES`, `POSTGRES_USER/PASSWORD/DB` | Docker, local DB | `localdb` starts the db container; credentials for it and the composed URL |
| `BOT_TOKEN` | yes | @BotFather |
| `OPENAI_API_KEY` | yes (prod) | Project with data-sharing enabled |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | no | Legacy provider |
| `TELEGRAM_API_ID/HASH/PHONE` | for scraping | my.telegram.org; without them the offline sample is used |
| `TG_SESSION` | no | Session path without `.session`. Default `yukdosh_session` (repo root); Docker: `/app/state/yukdosh_session` (volume `tgstate`) |
| `ADMIN_USER` / `ADMIN_PASSWORD` | yes (prod) | Empty password = admin auth OFF (dev only) |
| `OLLAMA_BASE_URL`, `LOCAL_MODEL` | no | Local parser (`http://localhost:11434/v1`, `qwen3:8b`) |
| `DOMAIN` | no | Only with `--profile https` (Caddy) |
| `PORT` | no | Web port for PaaS; default 8000 |

---

## 6. Parser

**Interface** (`parser/base.py`): `parse(text) -> list[ParsedLoad]`,
`parse_batch(texts) -> list[list[ParsedLoad]]` (default = loop over `parse`).
`factory.get_parser(provider, gemini_key, openai_key)` returns `OpenAIParser`,
`GeminiParser`, `LocalParser` or falls back to `MockParser` (prints why).

**Output schema** (`schemas.ParsedLoad`): all string fields default "", numbers None;
validators coerce lists→comma strings, "22-23т"→22.0, "yo'q"/"нет"/"bo'sh"→`is_load=False`.

**Prompt** (`parser/prompt.py`) = `SYSTEM_PROMPT` + `"DOMAIN NOTES"` (data/patterns.md) +
`"EXAMPLES"` (data/few_shot.jsonl, each rendered as `Message: …` / `JSON: …`). Built once per
process and cached (`_PROMPT_CACHE`) → **restart the scheduler after editing the prompt,
patterns or examples.** Identical prefix on every call → OpenAI prompt caching discount.

Key prompt rules: split EVERY direction into its own load; keep districts exactly
("Toshkent Yashnobod"); truck codes only from
`tent/ref/isotherm/flatbed/container/dump/isuzu/labo/paravoz`; "Сборка" is not a truck;
kg→tons; a date is never a price; cash without amount → "naqd" in comment; all phones on
every load; everything else → comment; skip loads missing origin or destination;
**omit empty fields** (saves output tokens).

Formats:
- single: user = "Extract EVERY load…" + text → `{"loads":[{…},…]}`
- batch: `### MESSAGE 1 … ### MESSAGE 10` → `{"results":[{"i":1,"loads":[…]},…]}`;
  `gemini.split_batch()` maps results back by `i` (missing = empty list).
- `gemini.to_loads()` converts any reply into `ParsedLoad`s (shared by all providers).

few_shot.jsonl line format:
```json
{"text": "<raw telegram post>", "output": {"loads": [{"origin_city": "...", "destination_city": "...", "truck_type": "tent", "contact_phone": "...", "comment": "..."}]}}
```
Currently 6 examples, chosen from real failures: 4-direction Cyrillic post (Рязань/Москва/
Алмата/Павлодар → Ташкент), urgent cash+dates post, Yashnobod district post, Labo/200 kg
post, empty truck, ad/junk. Keep the set small; replace weak examples instead of adding.

**Providers**
- `openai_p.OpenAIParser` — `gpt-4o-mini`, `response_format=json_object`, batched. PRODUCTION.
- `gemini.GeminiParser` — Google, resolves an available model name at init.
- `local_p.LocalParser` — Ollama OpenAI-compatible API; strips `<think>…</think>` and ```json
  fences; **no batching on purpose** (one message per call).
- `mock.MockParser` — regex heuristics; also provides `_find_price()` used by the bot's post flow.
- `groq.py` — unused leftover.

---

## 7. Normalisation, geo, dedup

**`parser/normalize.py`**
- `CITY_ALIASES` → `canonical_city(raw)` returns `(city, region)`; used for bot-posted loads.
- `TRUCK_ALIASES` → `canonical_truck`, `canonicalize_trucks(text)` scans free text for
  truck words (Latin/Cyrillic/typos via fuzzy match ≥0.82) and returns e.g. `"tent, ref"`.
  Includes `paravoz/паровоз/автопоезд` (road-train, listed IN ADDITION to tent/ref),
  `isuzu/исузу/isuzi`, `labo/лабо/labbo`.
- `norm_city()` transliterates Cyrillic→Latin and folds spelling variants;
  `city_match()` fuzzy comparison (difflib ≥0.8).

**`parser/geo.py`** — search hierarchy
- `_UZ_REGIONS` (region → districts), `_CIS_REGIONS`, `_COUNTRY_FLAT`, aliases for countries
  and regions, `_CITY_ALT` (canonical ↔ RU/UZ spellings: Бухара=Buxoro, Коканд=Qoqon,
  Джизак=Jizzax, Навои=Navoiy…), `_REGION_ALT`.
- `classify_query(q)` → country | region | city | any.
- `location_match(load_place, query)`: country → same country; region → load's region equals
  it (so "Qashqadaryo" finds Kitob, Qarshi); city → same canonical alias, else fuzzy.
- `_resolve_place(place)` (`lru_cache`d) → (region, country): whole name → without admin words
  (viloyati, область, shahri…) → word by word, also minus Uzbek case endings ("Киров Мураши",
  "Toshkentdan"; words < 4 letters only as a whole name) → fuzzy fallback (≥0.85) for typos.
  The fuzzy step can mislead (Чиназ≈China, Шардара≈Sirdaryo) — fix such cases by adding the
  exact spelling to `_COUNTRY_FLAT` / `_CITY_ALT`. `region_of` / `country_of` use it.
- `flag_of(place)` → `FLAGS[country_of(place)]` or "" — cards show the flag before each place
  (2026-10-16). 93% of 39,914 place mentions get a flag; ambiguous places get none on purpose
  (Хоргос — town on both the KZ and China side; Crimea).
- `has_known_place(text)` — used by the pipeline prefilter.

**`parser/dedup.py`** — `dedup_hash = sha(norm(origin)|norm(destination)|phones)` where
phones = every number reduced to its last 9 digits, sorted. No phone → route + cargo + weight.

---

## 8. Telegram bot (`app/bot/`)

aiogram 3, long polling (`dp.start_polling`) — no webhook, no inbound port needed.
`UsageMiddleware` calls `analytics.record_user()` on every update.

**Language:** `/start` and `/lang` show the picker (🇺🇿 O'zbekcha, 🇰🇿 Қазақша, 🇷🇺 Русский).
Choice saved in `bot_users.lang`; `get_lang()` caches per process. Default `uz`.
`t(lang, key, **fmt)` returns the string; `variants(key)` returns the same key in all languages
for button matching.

**Menu** (`menu_kb`): row 1 `➕ Yuk e'lonini berish`; row 2 `🔍 Yuk qidirish` | `🔔 Yo'nalishlarim`;
row 3 `🆕 Yangi yuklar` | `ℹ️ Yordam`.

**Flows**
- Search: FSM `Search.origin` → `Search.destination` ("-" = any) → inline truck picker
  (`st:<code>` / any) → `_send_page` shows 5 cards, `srch_more` for the next page.
  Search context is kept in an in-memory dict (`_search_ctx`) → lost on bot restart
  ("Qidiruv eskirgan" message).
- Latest: 10 newest active loads.
- Post a load: FSM `Post.filling` asks origin, destination, cargo, weight, price, phone
  ('-' skips). Saved with `listing_type="load"`, `source_group="bot"`, shown back as a card.
  (Goods/truck posting existed in an earlier version; the current menu only posts loads.)
- Saved routes: list with 🗑 delete buttons (`delsub:<id>`), `addroute` → origin →
  destination. Scheduler pushes matching new loads (max 10 per driver per run) in the
  driver's language, then marks loads `notified`.
- `/cancel` clears state; unknown text → menu hint.

**Card** (`formatting.format_load`):
```
<b>1.</b> 📦 <b>🇺🇿 Toshkent → 🇷🇺 Moskva</b>   ("1." only in multi-card messages; flag only when known)
🚚 Tent, Refrijerator ×2 · ⚖️ 20 t
📦 paxta
💰 45,000,000 so'm        (no price → "kelishiladi")
📞 +998 90 123 45 67
📝 comment
🕒 Bugun 16:54            (Tashkent time; "via bot" marker for bot posts)
```
Empty-truck cards use 🚛; goods listings have their own layout (`format_goods`). All load
fields are HTML-escaped. **No source link** (removed 2026-10-16): `formatting.original_kb()`
adds `📄 1…N` buttons (or one `📄 Asl matn` for a single card) with `callback_data="raw:<id>"`;
`cb_original` → `queries.original_text(id)` reads `raw_text` by primary key, cleans it with
`clean.clean_original` (unwraps Telegram markdown `[text](url)`, `**`, `__`; drops ad/promo lines —
other bots, channels, groups, freight apps (diip.uz, Yukon, Yukbozor, "ilovasi orqali…",
Play Market), bare domains, "Admin:", "kirish:", "orqali yuborildi" — then strips links,
domains, @mentions, #hashtags; `wa.me/+7…` keeps the number), caps at 3,800 chars
and sends it; a load already deleted by retention → "not found" alert. "Keyingi" keeps the
previous page's 📄 buttons. Rules were calibrated on 5,675 real posts (13 ad lines removed,
0 phones, 0 place names lost) and re-checked on 8,756 posts for the app rules (1,104 more ad
lines, 0 phones lost): "bot" only as a standalone word (-obot place names), "ilova" only at a
word start (surnames Isroilova, Komilova), no "Telegram" rule (contact lines), and lines
containing a 9+ digit phone are never dropped.

---

## 9. Web admin (`app/main.py`)

HTTP Basic auth middleware on everything except `/health` (off when `ADMIN_PASSWORD` empty).

| Route | Purpose |
|---|---|
| `GET /` | Dashboard: last 200 loads, raw-message count, last pipeline run result, Run button |
| `GET/POST /settings` | Settings form (§4) + groups list |
| `POST /groups/add`, `/groups/{id}/limits`, `/groups/{id}/toggle`, `/groups/{id}/delete` | Manage scraped groups |
| `POST /run` | Run pipeline in background (can't scrape in Docker web container — no session) |
| `GET /api/loads` | Last 500 loads as JSON |
| `GET /users` | Bot user analytics: total/new/active (24h/7d), searchable & sortable table, Tashkent time |
| `POST /targets/add`, `/targets/{id}/update`, `/targets/{id}/toggle`, `/targets/{id}/delete` | Groups the bot posts loads to (Settings page card "Groups to post loads to") |
| `GET /health` | `ok` (Docker healthcheck) |

---

## 10. CLI scripts (`py -m app.X` on Windows; `docker compose run --rm web python -m app.X`)

| Command | What it does | Run while app is… |
|---|---|---|
| `app.set_provider openai` | Set `parser_provider` (openai/gemini/local/mock) | any |
| `app.scraper.login` | One-time Telegram userbot login (code + 2FA) → session file. In Docker: `docker compose run --rm scheduler python -m app.scraper.login` | scheduler stopped |
| `app.scraper.logout` | Revoke session + delete file (switch account) | stopped |
| `app.dbview [loads N / raw N / subs]` | Inspect DB contents | any |
| `app.dbcheck` | Verify/apply column migrations | stopped |
| `app.diag` | Test the configured provider + show DB state | any |
| `app.clearqueue` | Clear raw queue + reset cursors (loads/routes/settings kept) | stopped |
| `app.reprocess` | Re-queue raw messages that produced no load | stopped |
| `app.export_samples [N]` | Dump raw posts to `data/real_samples.jsonl` for labelling | any |
| `app.reset` | Old one-time schema upgrade helper — avoid unless you know why | stopped |

---

## 11. Deployment

**Docker** (`Dockerfile`, `docker-compose.yml`): python:3.12-slim (multi-arch), non-root user
`yukdosh` (uid 1000), `TZ=Asia/Tashkent`. Services: `db` (postgres:16, volume `pgdata`, no host
port, **profile `localdb`**), `web` (127.0.0.1:8000 only, healthcheck `/health`), `bot`,
`scheduler` (volume `tgstate:/app/state` holds the Telegram session), optional `caddy` (profile
`https`, ports 80/443, needs `DOMAIN`). Shared settings via YAML anchor `x-app`; app services
`depends_on: db` with `required: false`; logs capped (10 MB × 3). `.dockerignore` excludes
`.env`, sessions, DBs, docs, `data/real_samples.jsonl`.

**Two DB modes, chosen in `.env`:**
- **local (production default):** `COMPOSE_PROFILES=localdb` + `POSTGRES_USER/PASSWORD/DB` →
  compose builds `DATABASE_URL=postgresql+asyncpg://…@db:5432/…`.
- **hosted (Supabase):** no `COMPOSE_PROFILES`, `.env` sets `DATABASE_URL` to the **Session
  pooler** URI (free plan: 500 MB, 5 GB/month egress, paused after 7 idle days, no backups).
The engine (`app/db.py`) uses small pools (3 + 2 overflow per process) with `pool_pre_ping` —
needed for the hosted pooler, harmless locally. Measured: 51 MB with ~20k loads over 16 days;
with 5-day retention the DB stays ~15–20 MB.

**Server: Azure VM `Standard_B2als_v2`** (2 vCPU / 4 GB, Central India, Ubuntu 24.04,
user `azureuser`) — full walkthrough in `DEPLOY.md`. Measured process RAM (startup): web 77 MB,
bot 156 MB, scheduler 175 MB → ~1–1.5 GB with Postgres + OS. Data + Telegram session are copied
from the PC (`pg_dump -Fc` → `pg_restore` in the db container; session file piped into the
`tgstate` volume). Daily `deploy/backup.sh` (local: `pg_dump` in the db container; hosted:
`postgres:17-alpine` client), keeps 14 `.dump` files in `backups/`. Updates:
`bash deploy/update.sh` (bot+web) or `... all`. Shrink path to the free 1 GB `B2ats_v2`:
move the DB to Supabase first (DEPLOY.md, last section). Never `docker compose down -v`.

---

## 12. Testing

- `py run_tests.py` — dependency-free runner; covers geo hierarchy (region→district, RU/UZ
  aliases), truck extraction (paravoz/isuzu/labo, typos), dedup (cross-group reposts), filters.
  Expected: `PASSED 17 FAILED 0` (number grows as tests are added).
- `pytest` (`tests/`, `pytest.ini`, `requirements-dev.txt`) — same areas, 12 test functions.
- There are no automated tests against the live LLM; accuracy is checked on real posts.
  When the owner reports a wrong parse: reproduce with `app.diag`/a small script, fix the
  prompt/few-shot/normalisation, add a regression test where deterministic.

---

## 13. Recipes

**Add a truck type** → CLAUDE.md rule 8 (five places + test). Restart scheduler and bot.

**Add a city spelling / district**
- Search matching: add to `_UZ_REGIONS` (district under region) and/or `_CITY_ALT`
  (canonical → aliases) in `geo.py`.
- Bot-post normalisation: `CITY_ALIASES` in `normalize.py`.
- Add a case to `tests/test_geo.py` / `run_tests.py`.

**Add/change a bot text** → edit `TEXTS` in `i18n.py` for `uz`, `kk` AND `ru`. Buttons must
be matched with `variants()`. Restart the bot.

**Add a DB column** → model field + `_WANTED_COLUMNS[table][col] = "<SQL type + default>"`.
Restart; `init_db` adds it. Check with `app.dbcheck`.

**Improve parsing for a failure** → add the real post + correct JSON to `few_shot.jsonl`
(replace a weaker example to keep ~6), or add a domain hint to `patterns.md` if it's a general
rule. Restart the scheduler (prompt cache). Re-queue affected messages with `app.reprocess`
if needed.

**Switch provider** → `app.set_provider openai|gemini|local|mock`, or Settings dropdown.

**Add a new language** → add a full `TEXTS["xx"]` dict + `LANG_NAMES["xx"]` + the code in
`lang_kb()`'s tuple.

**Promote a new process/service** → add a tuple in `runner.py` and a service in compose
using `<<: *app`.

---

## 14. Troubleshooting (errors we have actually hit)

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: DATABASE_URL is not set` | `.env` missing/wrong | Set it; never re-add SQLite fallback |
| `password authentication failed for user "yukdosh"` | `.env` had Docker creds but local native Postgres uses `postgres`/other password | Use the right user/password, URL-encode special chars |
| `ForeignKeyViolationError` deleting raw_messages | loads still point to them | Unlink `raw_message_id` first (already in pipeline & clearqueue) |
| `insufficient_quota` | OpenAI credit empty | Add credit / check data-sharing tier |
| `Rate limit … requests per day (RPD) Limit 10000` | Retry storm: failed calls retried every cycle and still counted | Batching + circuit breaker (in place); don't lower interval below ~1 min with a big backlog; `app.clearqueue` to drop a stale backlog |
| `ImportError: cannot import name 'batch_user_prompt'` | Function deleted from prompt.py | Restore it (see §6) |
| `pip.exe … blocked by Application Control` (Windows) | Policy | `py -m pip …` |
| `database is locked` | Old SQLite | Postgres only |
| Bot: `Conflict: terminated by other getUpdates request` | Bot running twice (PC + server) | Stop one |
| Scraper: "not logged in" / session revoked | No session in this environment, or session used on two machines | Run `app.scraper.login` in that environment; run scraper in one place only |
| Loads parsed but not shown in search | Older than `load_active_hours`, or place not matched | Check setting; add alias in geo.py |
| 1 new message, 0 loads | Prefilter judged it non-load, or parse returned no route | `app.dbview raw`, `app.diag`; improve few-shot |
| Local model: multi-direction posts collapse / dates as prices | Small model capacity | Use OpenAI (decision #5) |

---

## 15. Known issues / tech debt

- Renamed Sarbon24 → Sayyor (2026-09-28; competitor uses "Sarbon") → Yukdosh (2026-10-03).
  Domain, @BotFather bot username/display name, and pitch deck/research docs still need updating.
- `get_lang()` cache is per process: if a user switches language in the bot, the scheduler's
  notifications use the old language until the scheduler restarts.
- Saved routes don't ask for a truck type (`subscriptions.truck_type` always "").
- Search loads all active loads then filters in Python (raw_text is deferred, so ~a few hundred
  bytes per row). Each search still transfers the whole active window (matters for Supabase's
  5 GB/month egress in hosted mode); move geo filters into SQL (store canonical region/country
  columns) when it grows.
- Bot FSM + search pagination are in memory (lost on restart). Use a Redis/DB FSM storage later.
- No Alembic migrations — only additive column adds.
- `groq.py` unused; `app/reset.py` legacy.
- `data/real_samples.jsonl` is tracked in git and contains real phone numbers — consider
  removing it from the repo (keep locally) for privacy.
- The admin "Run pipeline now" cannot scrape in Docker (session only in scheduler).
- README/ARCHITECTURE mention older providers — this file + CLAUDE.md are authoritative.

---

## 16. Costs & limits (Sep 2026)

- **OpenAI gpt-4o-mini**: ~$0.15 / 1M input, $0.60 / 1M output tokens (verify current pricing).
  Data-sharing free tier: 2.5M tokens/day on mini models at usage tier 1–2 (resets 00:00 UTC;
  a request that would cross the limit is billed in full). Tier 3 ($100 lifetime spend) → 10M/day.
  OpenAI gives 30 days' notice before ending the program. Needs a positive account balance.
- Historic peak before optimisation: 7.7M tokens, 1,320 requests, $2.64 on 20 Jul 2026.
  Estimated after optimisation: ~250–350 tokens per message → ~0.4M tokens/day at that volume.
  2026-10-16: batches cut 10 → 5 (measured +20% loads found) → ~1.5× input tokens per message
  (the ~3.3k-token instructions repeat per call; OpenAI caches most of them).
- **Hosting**: Azure `Standard_B2als_v2` (Central India) ≈ $18/month + ~$5–10 (IP, disk,
  bandwidth); free via the $200 credit until 2026-11-14, then billed (account must be upgraded
  to pay-as-you-go before that date). Free fallback: Azure's 12-month free `B2ats_v2` (1 GB) with
  the DB on Supabase. Paid alternative: Hetzner (~€4–5/month for 2 vCPU / 4 GB).
- **Telegram**: userbot scraping of public groups; keep intervals reasonable to avoid flood
  limits (FloodWait).
