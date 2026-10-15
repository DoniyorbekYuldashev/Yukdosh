"""Yukdosh — FastAPI app: dynamic admin UI (groups + scrape window + parser) and
a dashboard of parsed loads. Protected by HTTP Basic auth in production."""
from pathlib import Path
import asyncio
import base64
import secrets

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response, PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select, desc, func, delete

from .db import init_db, SessionLocal
from .models import Group, Setting, Load, RawMessage, PostTarget, PostedLoad
from .pipeline import run_pipeline
from .broadcast import normalize_chat, MAX_LOADS_PER_POST
from .bot.formatting import TASHKENT, _TRUCK_KEYS
from .bot.queries import CARD_SOURCE_MODES
from .bot.i18n import LANG_NAMES
from . import config

TRUCK_CHOICES = [c for c in _TRUCK_KEYS if c != "other"]
POST_LANGS = tuple(LANG_NAMES)

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "web" / "templates"))

app = FastAPI(title="Yukdosh")

_last_run: dict = {}
_running: bool = False

# ── Admin authentication ────────────────────────────────────────────────────────
_OPEN_PATHS = {"/health"}  # reachable without a password (for uptime checks)


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Protect every route with HTTP Basic auth when ADMIN_PASSWORD is set.
    If it is empty, auth is disabled (local dev) — set it in production."""

    async def dispatch(self, request: Request, call_next):
        if not config.ADMIN_PASSWORD or request.url.path in _OPEN_PATHS:
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
                if (secrets.compare_digest(user, config.ADMIN_USER)
                        and secrets.compare_digest(pw, config.ADMIN_PASSWORD)):
                    return await call_next(request)
            except Exception:
                pass
        return Response("Unauthorized", status_code=401,
                        headers={"WWW-Authenticate": 'Basic realm="Yukdosh Admin"'})


app.add_middleware(BasicAuthMiddleware)


def _opt_int(v: str):
    v = (v or "").strip()
    return int(v) if v.isdigit() else None


@app.on_event("startup")
async def _startup():
    await init_db()


@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "ok"


async def _settings_dict(s) -> dict:
    rows = (await s.execute(select(Setting))).scalars().all()
    return {r.key: r.value for r in rows}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    async with SessionLocal() as s:
        loads = (await s.execute(select(Load).order_by(desc(Load.posted_at)).limit(200))).scalars().all()
        raw_count = (await s.execute(select(func.count()).select_from(RawMessage))).scalar_one()
    return templates.TemplateResponse(request, "dashboard.html", {
        "loads": loads, "raw_count": raw_count,
        "last_run": _last_run, "running": _running, "active": "dashboard",
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    async with SessionLocal() as s:
        cfg = await _settings_dict(s)
        groups = (await s.execute(select(Group).order_by(Group.id))).scalars().all()
        targets = (await s.execute(select(PostTarget).order_by(PostTarget.id))).scalars().all()
    last_post = {tg.id: tg.last_posted_at.astimezone(TASHKENT).strftime("%d.%m %H:%M")
                 for tg in targets if tg.last_posted_at}
    return templates.TemplateResponse(request, "settings.html", {
        "cfg": cfg, "groups": groups, "active": "settings",
        "targets": targets, "last_post": last_post, "truck_choices": TRUCK_CHOICES,
        "post_langs": POST_LANGS, "max_per_post": MAX_LOADS_PER_POST,
    })


@app.post("/settings")
async def save_settings(
    scrape_max_messages: int = Form(50),
    scrape_hours_back: int = Form(24),
    parser_provider: str = Form("mock"),
    gemini_api_key: str = Form(""),
    openai_api_key: str = Form(""),
    scheduler_enabled: str = Form(""),          # checkbox -> "on" when checked
    scheduler_interval_minutes: int = Form(10),
    load_active_hours: int = Form(12),
    load_retention_days: int = Form(5),
    card_source_mode: str = Form("original"),
):
    updates = {
        "card_source_mode": card_source_mode if card_source_mode in CARD_SOURCE_MODES else "original",
        "scrape_max_messages": str(scrape_max_messages),
        "scrape_hours_back": str(scrape_hours_back),
        "parser_provider": parser_provider,
        "gemini_api_key": gemini_api_key.strip(),
        "openai_api_key": openai_api_key.strip(),
        "scheduler_enabled": "true" if scheduler_enabled else "false",
        "scheduler_interval_minutes": str(scheduler_interval_minutes),
        "load_active_hours": str(load_active_hours),
        "load_retention_days": str(max(0, load_retention_days)),
    }
    async with SessionLocal() as s:
        for k, v in updates.items():
            row = (await s.execute(select(Setting).where(Setting.key == k))).scalar_one_or_none()
            if row:
                row.value = v
            else:
                s.add(Setting(key=k, value=v))
        await s.commit()
    return RedirectResponse("/settings", status_code=303)


@app.post("/groups/add")
async def add_group(
    link: str = Form(...),
    title: str = Form(""),
    max_messages: str = Form(""),
    hours_back: str = Form(""),
):
    link = link.strip()
    if link:
        async with SessionLocal() as s:
            exists = (await s.execute(select(Group).where(Group.link == link))).scalar_one_or_none()
            if not exists:
                s.add(Group(
                    link=link, title=title.strip(), enabled=True,
                    max_messages=_opt_int(max_messages), hours_back=_opt_int(hours_back),
                ))
                await s.commit()
    return RedirectResponse("/settings", status_code=303)


@app.post("/groups/{group_id}/limits")
async def update_limits(group_id: int, max_messages: str = Form(""), hours_back: str = Form("")):
    async with SessionLocal() as s:
        g = (await s.execute(select(Group).where(Group.id == group_id))).scalar_one_or_none()
        if g:
            g.max_messages = _opt_int(max_messages)
            g.hours_back = _opt_int(hours_back)
            await s.commit()
    return RedirectResponse("/settings", status_code=303)


@app.post("/groups/{group_id}/toggle")
async def toggle_group(group_id: int):
    async with SessionLocal() as s:
        g = (await s.execute(select(Group).where(Group.id == group_id))).scalar_one_or_none()
        if g:
            g.enabled = not g.enabled
            await s.commit()
    return RedirectResponse("/settings", status_code=303)


@app.post("/groups/{group_id}/delete")
async def delete_group(group_id: int):
    async with SessionLocal() as s:
        g = (await s.execute(select(Group).where(Group.id == group_id))).scalar_one_or_none()
        if g:
            await s.delete(g)
            await s.commit()
    return RedirectResponse("/settings", status_code=303)


def _target_fields(interval_minutes, loads_per_post, origin, destination, truck_type, lang) -> dict:
    return {
        "interval_minutes": max(1, interval_minutes),
        "loads_per_post": min(MAX_LOADS_PER_POST, max(1, loads_per_post)),
        "origin": origin.strip(), "destination": destination.strip(),
        "truck_type": truck_type if truck_type in TRUCK_CHOICES else "",
        "lang": lang if lang in POST_LANGS else "uz",
    }


@app.post("/targets/add")
async def add_target(
    chat: str = Form(...), title: str = Form(""), interval_minutes: int = Form(60),
    loads_per_post: int = Form(5), origin: str = Form(""), destination: str = Form(""),
    truck_type: str = Form(""), lang: str = Form("uz"),
):
    chat = normalize_chat(chat)
    if chat:
        async with SessionLocal() as s:
            exists = (await s.execute(select(PostTarget).where(PostTarget.chat == chat))).scalar_one_or_none()
            if not exists:
                s.add(PostTarget(chat=chat, title=title.strip(), enabled=True, **_target_fields(
                    interval_minutes, loads_per_post, origin, destination, truck_type, lang)))
                await s.commit()
    return RedirectResponse("/settings", status_code=303)


@app.post("/targets/{target_id}/update")
async def update_target(
    target_id: int, interval_minutes: int = Form(60), loads_per_post: int = Form(5),
    origin: str = Form(""), destination: str = Form(""), truck_type: str = Form(""),
    lang: str = Form("uz"),
):
    async with SessionLocal() as s:
        tg = (await s.execute(select(PostTarget).where(PostTarget.id == target_id))).scalar_one_or_none()
        if tg:
            for k, v in _target_fields(interval_minutes, loads_per_post, origin, destination,
                                       truck_type, lang).items():
                setattr(tg, k, v)
            await s.commit()
    return RedirectResponse("/settings", status_code=303)


@app.post("/targets/{target_id}/toggle")
async def toggle_target(target_id: int):
    async with SessionLocal() as s:
        tg = (await s.execute(select(PostTarget).where(PostTarget.id == target_id))).scalar_one_or_none()
        if tg:
            tg.enabled = not tg.enabled
            await s.commit()
    return RedirectResponse("/settings", status_code=303)


@app.post("/targets/{target_id}/delete")
async def delete_target(target_id: int):
    async with SessionLocal() as s:
        await s.execute(delete(PostedLoad).where(PostedLoad.target_id == target_id))
        await s.execute(delete(PostTarget).where(PostTarget.id == target_id))
        await s.commit()
    return RedirectResponse("/settings", status_code=303)


async def _bg_run():
    global _last_run, _running
    _running = True
    try:
        _last_run = await run_pipeline()
    except Exception as exc:
        _last_run = {"error": str(exc), "provider": "-", "groups_scanned": 0,
                     "new_raw_messages": 0, "loads_created": 0, "duplicates_skipped": 0,
                     "junk_skipped": 0, "window": {"max_messages": 0, "hours_back": 0}}
    finally:
        _running = False


@app.post("/run")
async def run_now():
    if not _running:
        asyncio.create_task(_bg_run())
    return RedirectResponse("/", status_code=303)


@app.get("/api/loads", response_class=JSONResponse)
async def api_loads():
    async with SessionLocal() as s:
        loads = (await s.execute(select(Load).order_by(desc(Load.posted_at)).limit(500))).scalars().all()
    return [{
        "is_load": l.is_load, "origin": l.origin_city, "destination": l.destination_city,
        "cargo_type": l.cargo_type, "weight_tons": float(l.weight_tons) if l.weight_tons else None,
        "truck_type": l.truck_type, "price_amount": float(l.price_amount) if l.price_amount else None,
        "price_currency": l.price_currency, "phone": l.contact_phone,
        "language": l.language_detected, "provider": l.parser_provider, "source_group": l.source_group,
    } for l in loads]


_USERS_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Foydalanuvchilar - Yukdosh</title>
<style>
body{font-family:system-ui,'Segoe UI',Arial,sans-serif;margin:24px;color:#132539;background:#f8fafc}
h2{margin:0 0 4px;font-weight:600}
.sub{color:#64748b;font-size:13px;margin-bottom:18px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 18px;min-width:118px}
.card b{font-size:26px;color:#0F766E;display:block;line-height:1.2}
.card span{font-size:13px;color:#64748b}
.bar{display:flex;gap:10px;align-items:center;margin-bottom:10px}
input{flex:1;max-width:280px;padding:8px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px}
input:focus{outline:none;border-color:#0F766E}
button{padding:8px 14px;border:1px solid #0F766E;background:#0F766E;color:#fff;border-radius:8px;cursor:pointer;font-size:14px}
button:hover{background:#0b5f59}
table{border-collapse:collapse;width:100%;background:#fff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}
th,td{border-bottom:1px solid #eef2f7;padding:9px 12px;text-align:left;font-size:14px}
th{color:#475569;font-weight:500;cursor:pointer;user-select:none;background:#f1f5f9}
th:hover{color:#0F766E}
td.num,th.num{text-align:right}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:#f8fafc}
a{color:#0F766E;text-decoration:none}
.count{color:#64748b;font-size:13px}
</style></head><body>
<h2>Foydalanuvchilar</h2>
<div class="sub">Vaqt: Toshkent (UTC+5) &middot; <a href="/">&larr; Boshqaruv paneli</a></div>
<div class="cards">__CARDS__</div>
<div class="bar">
  <input id="q" placeholder="Qidirish: @username yoki ism...">
  <span class="count" id="cnt"></span>
  <button onclick="location.reload()">Yangilash</button>
</div>
<table id="t"><thead><tr>
<th onclick="sortBy(0)">Foydalanuvchi</th>
<th onclick="sortBy(1)">Birinchi kirgan</th>
<th onclick="sortBy(2)">Oxirgi faollik</th>
<th class="num" onclick="sortBy(3)">Amallar</th>
</tr></thead><tbody>__ROWS__</tbody></table>
<script>
var tb=document.querySelector('#t tbody'),q=document.getElementById('q'),cnt=document.getElementById('cnt'),dir={};
function rows(){return Array.prototype.slice.call(tb.querySelectorAll('tr'));}
function upd(){var v=q.value.toLowerCase(),n=0;rows().forEach(function(r){
  var s=r.cells[0].textContent.toLowerCase(),show=!v||s.indexOf(v)>-1;
  r.style.display=show?'':'none';if(show)n++;});cnt.textContent=n+' ta';}
function sortBy(i){dir[i]=!dir[i];var s=dir[i]?1:-1;var rs=rows();
  rs.sort(function(a,b){var av=a.cells[i].dataset.v||a.cells[i].textContent,
    bv=b.cells[i].dataset.v||b.cells[i].textContent,na=parseFloat(av),nb=parseFloat(bv);
    if(!isNaN(na)&&!isNaN(nb))return (na-nb)*s;return av.localeCompare(bv)*s;});
  rs.forEach(function(r){tb.appendChild(r);});}
q.addEventListener('input',upd);upd();
</script></body></html>"""


@app.get("/users", response_class=HTMLResponse)
async def users_page():
    import html as _html
    from datetime import timezone as _tz, timedelta as _td
    from . import analytics

    tashkent = _tz(_td(hours=5))          # loads/users are stored in UTC; show local time
    st = await analytics.get_stats()

    def _local(dt):
        if not dt:
            return "-", 0
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz.utc)
        return dt.astimezone(tashkent).strftime("%d.%m.%Y %H:%M"), int(dt.timestamp())

    rows = []
    for u in st["recent"]:
        who = ("@" + u.username) if u.username else (u.first_name or u.tg_user_id)
        first_txt, first_ts = _local(u.first_seen)
        last_txt, last_ts = _local(u.last_seen)
        acts = u.actions or 0
        rows.append(
            "<tr><td>" + _html.escape(who) + "</td>"
            f'<td data-v="{first_ts}">{first_txt}</td>'
            f'<td data-v="{last_ts}">{last_txt}</td>'
            f'<td class="num" data-v="{acts}">{acts}</td></tr>'
        )

    cards = "".join(
        f'<div class="card"><b>{val}</b><span>{label}</span></div>'
        for val, label in (
            (st["total"], "Jami foydalanuvchi"),
            (st["new1"], "Bugun yangi"),
            (st["new7"], "7 kunda yangi"),
            (st["act1"], "24 soatda faol"),
            (st["act7"], "7 kunda faol"),
        )
    )
    page = _USERS_HTML.replace("__CARDS__", cards).replace("__ROWS__", "".join(rows))
    return HTMLResponse(page)
