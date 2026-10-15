# Product, business & decision history

Everything non-code about the project: what it is, who it's for, how it makes money, who
the competitors are, the naming situation, and **why** each big decision was made — so
nobody has to re-derive it. Facts about competitors come from web research done in
July–September 2026; re-check before using them in front of investors.

---

## 1. One-line pitch

> Loads are posted chaotically in dozens of Telegram groups. We collect them automatically,
> clean them up with AI, and send each driver only the loads on his route — inside Telegram,
> no app, no registration, contacts always free.

Pitch-deck tagline (Uzbek): *"Yo'nalishingizni saqlang — yangi yuklar o'zi keladi."*
("Save your route — new loads come to you.")

---

## 2. The problem

- Freight in Uzbekistan/Central Asia is traded in **public Telegram groups**. A driver follows
  10–20 groups and scrolls hundreds of posts a day, written in Uzbek (Latin AND Cyrillic),
  Russian and Kazakh, full of typos, emojis and abbreviations.
- A load owner reposts the same load into dozens of groups to be seen → massive duplication.
- Trucks often return empty (**backhaul**) — pure loss for the driver.
- Existing platforms put phone numbers behind a paywall, so drivers go back to free groups.

## 3. Who uses it

| Side | Today | Later |
|---|---|---|
| **Truck drivers / owner-operators** (main user now) | search loads, save routes, get notified | premium features |
| **Load owners / shippers / dispatchers** | can post a load in the bot | promoted posts, dispatcher subscriptions |
| **Goods sellers & buyers** | — (vision) | marketplace: seller lists goods, buyer buys, driver delivers |

Language priority: Uzbek → Kazakh → Russian (all three are implemented in the bot).
Small trucks (Isuzu, Labo) and road-trains ("paravoz") plus district-level search are a
deliberate niche that big platforms cover poorly.

## 4. The full vision (3-sided marketplace)

1. **Now — liquidity:** aggregate every public load so drivers find everything in one place.
2. **Two-sided:** shippers post directly in the bot (first revenue).
3. **Trust layer:** ratings, deal records inside the app, documents (zayavka / waybill).
4. **Goods marketplace:** a seller lists goods (like Uzum Market, but B2B/commodities), a buyer
   buys, and if neither has a truck the deal becomes a load that a driver accepts and
   delivers. Commission on the goods deal + freight.
5. **Financial services** with partners (payments, factoring, insurance).

## 5. Business model (from the pitch deck; prices in UZS)

**Rule: a driver never pays to see a contact.** Revenue comes from those who want to reach drivers.

| Stage | When | Who pays | Price |
|---|---|---|---|
| Build liquidity | now – 6 months | nobody | 0 |
| Promote a load post to the top | 6–12 months | load owner | 5,000–20,000 so'm / post |
| Dispatcher subscription | 6–12 months | logistics company | 200,000–500,000 so'm / month |
| Driver premium (optional) | 12–24 months | driver | 20,000–35,000 so'm / month |
| Financial services | 24+ months | partners | 1–3% of freight value |
| Marketplace | 24+ months | sellers | 2–5% commission |

Market sizing used in the deck (estimates): TAM ≈ $21B/yr Central Asian road freight
(KZ ≈ $17B, UZ ≈ $2.8B, KG+TJ ≈ $1B); SAM ≈ $1.7B Uzbek spot market; SOM $200–400k ARR in
3 years in Uzbekistan. Brokerage/dispatch layer ≈ 10–15% of freight spend. Benchmark: Full
Truck Alliance (China) consolidated a fragmented ~$800B market.

---

## 6. Competitors (as researched; verify before reuse)

| Competitor | What it is | Notes |
|---|---|---|
| **Sarbon** (Google Play, IT GENIUS MCHJ, Tashkent) | Load search app for drivers: filters, notifications, ratings, distance calc, vehicle sales. 1K+ downloads, updated Sep 2026. Also appeared under the name **Furgo**. | **Same niche AND same name → we must rename.** |
| **Diip.uz** | Strongest local rival: ~$205k raised, Telegram AI, mini-app, 9 languages | Contacts limited for free users; focused on long-haul/international |
| **Yuk.uz** | "Unified logistics platform" — loads + trucks, Uzbekistan/CIS/China, iOS+Android, in-app waybills, powers of attorney, acts, chat | Serious, well-built, document workflow — add to the pitch deck |
| **Yukbozor.uz** | Contract/order platform | Slow for spot loads |
| **Yuk Markazi (yukmarkazi.uz)** | Logistics company + app (transport, storage) | |
| **Yukla** | App to order heavy cargo transport / special equipment | Different segment |
| **Cargoinfo.UZ / Cargo.KZ** | Classic load boards (claim 25k cargo + 15k truck offers/day across CIS/Asia/EU) | Company-oriented, paid |
| **Reis** (Kazakhstan) | Cargo app, 18,000+ participants | Relevant for KZ expansion |
| **Fura** | Eurasia-wide driver/shipper app (return loads, chat) | |
| **ATI.su, Otborta, Perevozka24** | Russian load exchanges | Used for RU↔CA lanes |
| **Telegram groups** | Where the market lives today | We don't fight them — they are our supply |
| **inDrive / Yango** | City delivery | Not long-haul freight |

**Our edge:** contacts always free · no app, no registration (lowest friction) · district-level
search in 3 languages & 2 scripts · small-truck niche · automatic aggregation of ALL groups.

**"Are we just an AI wrapper?"** The LLM call is replaceable (we already switched providers
several times). The moat has to be what others can't copy quickly: (1) the growing labelled
dataset of real Central Asian freight posts (few-shot today, fine-tuning later), (2) liquidity
and network effects — drivers + shippers in one place, (3) geo/district and alias data,
(4) distribution inside Telegram, (5) workflow later — trust, deal records, documents.

---

## 7. Naming (decided — current name Yukdosh, since 2026-10-03)

**Current name: Yukdosh.** History: **Sarbon24** ("sarbon" = caravan leader; "24" = always
on) → changed 2026-09-28 to **Sayyor** because a direct competitor is called **Sarbon** (see
§6) → changed 2026-10-03 to **Yukdosh**, a name the owner found himself. Code-level rename
(bot texts, admin, logo, docs, infra identifiers) and the GitHub repo rename (→ `Yukdosh`) are
done. Still open: domain, Telegram bot username and trademark checks below, @BotFather display
name, and the pitch deck/research documents (still titled `Sarbon24_*`).

⚠ Yukdosh has **not** been conflict-checked. It shares the "Yuk-" prefix with competitors
already listed below (Yuk.uz, Yukbozor.uz, Yukla, Yuk Markazi), so it is descriptive-sounding
and easy to confuse with them — weaker trademark distinctiveness. Check before investing in
branding.

Checked and **taken / conflicting** (don't propose again): Sarbon, Furgo, Fura, Yukla, Bormi
(discounts app), Juft (dating), Karvon/Caravan (several companies incl. Caravan Logistics in
UZ/KZ), Silk (freight platform, SilkWay Cargo, Silq), Oasis (Oasis Logistics KZ), Arba (US
freight OS), Tulpar (KZ taxi+cargo app, Tulpar Logistics), Haulo, Chapar (Iran courier), Ulak
(Turkish delivery), Reys/Reis, Poputka, Sinbad/Sindbad (B2B marketplace), Marco (warehouse
app), Ortaq (KZ marketplace tool), Karvo (fitness app), Yuk.uz.

Candidates with **no conflict found in web searches** (NOT legally cleared): **Sayyor**
(chosen 2026-09-28, replaced by Yukdosh 2026-10-03), Stork, Ulov, Ortoq, Sogdi, Rulda, Qatnov, Bekat, Tashuv, Yukli, Yukgo, Pelican.

Honest ranking given to the owner: **Sayyor > Stork > Sarbon24**.
- Sayyor — "always on the move" (uz/tj), close to *sayyora* (planet); local and trustworthy
  like "Uzum"; fits the whole marketplace; easy in Russian (Сайёр). Minus: abstract, double-y
  misspellings (also get sayor.uz if possible).
- Stork — international, "delivers", but means nothing to Uzbek drivers and in the CIS
  "Аист" is a baby/maternity brand.

Before finalising: check domain at cctld.uz, Telegram bot username, Instagram, trademark at
ima.uz (Intellectual Property Agency). Rename touches: i18n texts (welcome/help), web
titles, README/docs, logo wordmark (assets/), pitch deck, bot display name in @BotFather.

Brand assets: final logo = truck + guiding star, single teal `#0F766E`, minimal lines
(owner asked "do not overshoot with colors and lines"). Files in `assets/`.

---

## 8. Roadmap

1. **Now:** deploy on Oracle Always Free; verify phone masking live; watch token usage.
2. Rename (after checks).
3. Grow drivers in Uzbekistan (promo copy in uz/ru exists; exact button names must match).
4. Shippers post directly → promoted posts + dispatcher subscriptions (first revenue).
5. Ratings/trust, in-app deal records, documents (zayavka, waybill; CMR/TIR researched).
6. Kazakhstan (6× bigger market), then Kyrgyzstan/Tajikistan.
7. Goods marketplace + financial services.
8. Fine-tune a model on the labelled data when volume justifies it.

---

## 9. Decision log (what we chose and WHY)

| # | Decision | Why / what was rejected |
|---|---|---|
| 1 | **Scrape on a schedule → store → serve from DB** | Parse each post once and serve unlimited times; instant search; controlled Telegram load. Rejected: scrape+parse per driver query (slow, costly, ban risk). |
| 2 | **Telegram bot, not a mobile app** | Drivers already live in Telegram; zero install/registration = lowest friction. |
| 3 | **Contacts always free** | Direct answer to competitors' paywalls; drivers otherwise return to free groups. |
| 4 | **Prompting + few-shot, not fine-tuning (yet)** | Fast to iterate; the labelled examples are kept as the future fine-tuning asset. |
| 5 | **Parser provider: OpenAI gpt-4o-mini** | Journey: Groq free (rate limits) → Gemini free → OpenAI (reliable). Local Qwen3 8B/14B on the owner's Ubuntu GPU box (RTX 5080 16 GB) tested and rejected: kept dropping districts, merging multi-direction posts, reading dates as prices. |
| 6 | **Batching 10 msgs/call + circuit breaker + local prefilter** | A retry storm once burned the whole 10,000 requests/day OpenAI limit in ~90 min (failed calls still count). Fixes cut requests ~10× and stop a run when a whole wave fails. |
| 7 | **Token savings "1+2+3"** | Trimmed patterns.md (~821→~148 tokens), few-shot 12→6 real-failure examples, compressed system prompt (~875→~582) + omit-empty-fields output. Rejected: translating posts to English first (adds a call, loses nuance). |
| 8 | **OpenAI data-sharing free tier** | 2.5M free tokens/day on mini models at tier 1–2 (tier 3 = $100 lifetime spend → 10M). Enabled for the project. Estimated usage after optimisations ≈ 400K tokens/day on the busiest historical day (pre-optimisation peak was 7.7M tokens / 1,320 requests on 20 Jul 2026). |
| 9 | **Mask phone numbers before any API call** | Owner's privacy/legal concern: even public data shouldn't be shipped to a third party with personal numbers. Regex masking costs microseconds; re-attachment never blanks a phone. |
| 10 | **PostgreSQL only** | SQLite caused "database is locked" and hid FK bugs; a silent SQLite fallback once ran the app on the wrong DB. |
| 11 | **Geo hierarchy search** | Drivers search "Qashqadaryo" and expect Kitob/Qarshi; RU and UZ spellings must match. |
| 12 | **Dedup on route + phone (last 9 digits)** | Same load reposted across groups with different wording/price must show once. |
| 13 | **Split processes** (scraper vs bot+web) | UI changes no longer interrupt scraping; in Docker each is its own service. |
| 14 | **Hosting: Oracle Cloud Always Free (ARM A1)** | Railway trial needed a paid upgrade; running on the owner's PC 24/7 rejected; Hugging Face Spaces wrong shape for 24/7 workers + persistent Telegram session; GCP free e2-micro too small; AWS free only 12 months. Paid fallback: Hetzner CX22 (~€4/mo). Oracle may reclaim idle free VMs → upgrade account to Pay-As-You-Go (still $0 in free limits). |
| 15 | **Admin via SSH tunnel, no domain** | Admin is only for the owner; nothing exposed to the internet except SSH. Caddy/HTTPS available later via `--profile https`. |
| 16 | **Card UI choices** | Removed poster @username; removed "manba: @group" line (the 🔗 E'lon manbasi link is enough); price missing → "kelishiladi"; menu: search left, routes right. |
| 17 | **Rename Sarbon24 → Sayyor** | Competitor "Sarbon" (IT GENIUS MCHJ) is same niche, same name. Owner picked Sayyor over Stork (Sayyor is local/Uzbek-rooted; Stork means nothing to Uzbek drivers and reads as a maternity brand in CIS). Confirmed 2026-09-28; superseded by #18. |
| 21 | **Replace "🔗 E'lon manbasi" with a "📄 Asl matn" button** | The link revealed the source group, taught drivers to bypass the bot and made it look like a reposter. Removing it outright would lose the only way to check AI parsing mistakes, so the original post text is shown inside the bot instead, with links/@mentions stripped. Attribution was not real legal cover anyway (facts aren't copyrightable; the real issue is personal data — phones — and Uzbekistan's data-localization rule; get legal advice before scaling). Decided 2026-10-16. |
| 20 | **Hosting: one Azure VM (B2als_v2, 2 vCPU / 4 GB, Central India) with Postgres in Docker** | Owner opened an Azure free account ($200 credit, 30 days) and chose to keep paying ~$20–28/month afterwards rather than squeeze into a 1 GB free VM. DB stays on the VM (simplest, no Supabase limits); Supabase remains a one-setting switch (`.env`) if he shrinks to the free 12-month B2ats_v2 later. Decided 2026-10-15; supersedes #19's hosting part. |
| 19 | **Hosting: Supabase DB + Oracle E2.1.Micro app; loads kept 5 days; 12h search window** | Oracle Ampere was out of capacity in Mumbai at every size, a second Oracle account was blocked as a duplicate, Google's $300 trial needed a prepayment, Azure for Students couldn't verify PDP University, and Fly.io/Koyeb/Railway/HF Spaces have no free always-on worker + storage. Moving Postgres to Supabase frees the micro VM's 1 GB for the 3 Python processes (~500–600 MB measured). Loads older than 5 days are deleted (they're taken long before; keeps the DB under 500 MB). Owner widened the search window 6h → 12h so quiet routes still show loads (2026-10-05). |
| 18 | **Rename Sayyor → Yukdosh** | Owner found the name Yukdosh himself and chose it over Sayyor (2026-10-03). Not conflict-checked; shares the "Yuk-" prefix with competitors Yuk.uz / Yukbozor.uz / Yukla. |

---

## 10. Other documents in the repo

- `Sarbon24_Pitch_Deck.pdf` — 8 slides in Uzbek (problem, solution, how it works, market,
  business model, competition, roadmap). "Ask" and "Risks" slides removed on purpose.
- `Sarbon24_Competitive_Analysis.docx`, `Sarbon24_Competitive_Regulatory_Brief.docx`
  (CMR, TIR, e-invoicing, legal requirements), `Sarbon24_Regional_Expansion_Research.docx`
  (cross-border barriers, KZ/KG/TJ).
