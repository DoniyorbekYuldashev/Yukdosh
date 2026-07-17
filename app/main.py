"""Sarbon24 — FastAPI app: dynamic admin UI (groups + scrape window + parser) and
a dashboard of parsed loads. Protected by HTTP Basic auth in production."""
from pathlib import Path
import asyncio
import base64
import secrets

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response, PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select, desc

from .db import init_db, SessionLocal
from .models import Group, Setting, Load, RawMessage
from .pipeline import run_pipeline
from . import config

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "web" / "templates"))

app = FastAPI(title="Sarbon24")

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
                        headers={"WWW-Authenticate": 'Basic realm="Sarbon24 Admin"'})


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
        raw_count = (await s.execute(select(RawMessage))).scalars().all()
    return templates.TemplateResponse(request, "dashboard.html", {
        "loads": loads, "raw_count": len(raw_count),
        "last_run": _last_run, "running": _running, "active": "dashboard",
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    async with SessionLocal() as s:
        cfg = await _settings_dict(s)
        groups = (await s.execute(select(Group).order_by(Group.id))).scalars().all()
    return templates.TemplateResponse(request, "settings.html", {
        "cfg": cfg, "groups": groups, "active": "settings",
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
    load_active_hours: int = Form(6),
):
    updates = {
        "scrape_max_messages": str(scrape_max_messages),
        "scrape_hours_back": str(scrape_hours_back),
        "parser_provider": parser_provider,
        "gemini_api_key": gemini_api_key.strip(),
        "openai_api_key": openai_api_key.strip(),
        "scheduler_enabled": "true" if scheduler_enabled else "false",
        "scheduler_interval_minutes": str(scheduler_interval_minutes),
        "load_active_hours": str(load_active_hours),
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
