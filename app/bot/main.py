"""Yukdosh driver bot (aiogram v3) — multilingual: Uzbek, Kazakh, Russian.

Every user-facing string comes from i18n.t(lang, key). Menu buttons are matched across
ALL languages, so a user who switched language still hits the right handler.
Run:  python -m app.bot.main   (needs BOT_TOKEN in .env)
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (Message, ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery)

from ..config import BOT_TOKEN
from ..db import init_db
from ..analytics import record_user
from ..parser.mock import _find_price
from ..parser.normalize import canonical_city
from . import queries, subscriptions
from .formatting import format_results, format_load
from .i18n import t, variants, LANG_NAMES, get_lang, set_lang

logging.basicConfig(level=logging.INFO)
router = Router()

PAGE_SIZE = 5
_search_ctx: dict = {}
TRUCK_CODES = ["tent", "ref", "isotherm", "flatbed", "container", "dump", "isuzu", "paravoz", "labo"]
SEQ = ["origin", "destination", "cargo", "weight", "price", "phone"]
PROMPT_KEY = {"origin": "p_origin", "destination": "p_dest", "cargo": "p_cargo",
              "weight": "p_weight", "price": "p_price", "phone": "p_phone"}


class UsageMiddleware(BaseMiddleware):
    """Record every interacting user for analytics (count, first/last seen)."""
    async def __call__(self, handler, event, data):
        try:
            await record_user(data.get("event_from_user"))
        except Exception as exc:
            logging.warning(f"usage track failed: {exc}")
        return await handler(event, data)


class Search(StatesGroup):
    origin = State()
    destination = State()


class Post(StatesGroup):
    filling = State()


class Route(StatesGroup):
    origin = State()
    destination = State()


# ── keyboards ──
def menu_kb(lang) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_post"))],
            [KeyboardButton(text=t(lang, "btn_search")), KeyboardButton(text=t(lang, "btn_routes"))],
            [KeyboardButton(text=t(lang, "btn_latest")), KeyboardButton(text=t(lang, "btn_help"))],
        ],
        resize_keyboard=True,
    )


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANG_NAMES[code], callback_data=f"lang:{code}")]
        for code in ("uz", "kk", "ru")
    ])


def truck_kb(lang) -> InlineKeyboardMarkup:
    rows, row = [], []
    for code in TRUCK_CODES:
        row.append(InlineKeyboardButton(text=t(lang, "tk_" + code), callback_data=f"st:{code}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t(lang, "truck_any"), callback_data="st:any")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── language ──
@router.message(Command("start"))
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(t(await get_lang(m.from_user.id), "choose_lang"), reply_markup=lang_kb())


@router.message(Command("lang"))
async def cmd_lang(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(t(await get_lang(m.from_user.id), "choose_lang"), reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = cb.data.split(":", 1)[1]
    await set_lang(cb.from_user.id, lang)
    await cb.answer(t(lang, "lang_set"))
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.message.answer(t(lang, "welcome"), reply_markup=menu_kb(lang))


@router.message(Command("cancel"))
async def cmd_cancel(m: Message, state: FSMContext):
    lang = await get_lang(m.from_user.id)
    await state.clear()
    await m.answer(t(lang, "cancelled"), reply_markup=menu_kb(lang))


@router.message(F.text.in_(variants("btn_help")))
async def on_help(m: Message):
    lang = await get_lang(m.from_user.id)
    await m.answer(t(lang, "help"), reply_markup=menu_kb(lang))


# ── browse / search ──
@router.message(F.text.in_(variants("btn_latest")))
async def on_latest(m: Message):
    lang = await get_lang(m.from_user.id)
    loads = await queries.latest_loads(10)
    await m.answer(format_results(loads, t(lang, "latest_title"), lang), reply_markup=menu_kb(lang))


@router.message(F.text.in_(variants("btn_search")))
async def on_search(m: Message, state: FSMContext):
    lang = await get_lang(m.from_user.id)
    await state.set_state(Search.origin)
    await m.answer(t(lang, "ask_origin"))


@router.message(Search.origin)
async def search_origin(m: Message, state: FSMContext):
    lang = await get_lang(m.from_user.id)
    await state.update_data(origin=(m.text or "").strip())
    await state.set_state(Search.destination)
    await m.answer(t(lang, "ask_dest"))


@router.message(Search.destination)
async def search_dest(m: Message, state: FSMContext):
    lang = await get_lang(m.from_user.id)
    data = await state.get_data()
    origin = data.get("origin", "")
    dest = (m.text or "").strip()
    origin = "" if origin in ("-", "—") else origin
    dest = "" if dest in ("-", "—", "") else dest
    await state.clear()
    _search_ctx[m.from_user.id] = {"origin": origin, "dest": dest, "truck": "", "offset": 0}
    await m.answer(t(lang, "ask_truck"), reply_markup=truck_kb(lang))


@router.callback_query(F.data.startswith("st:"))
async def cb_search_truck(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    await cb.answer()
    ctx = _search_ctx.get(cb.from_user.id)
    if not ctx:
        await cb.message.answer(t(lang, "search_expired"), reply_markup=menu_kb(lang))
        return
    code = cb.data.split(":", 1)[1]
    truck = "" if code == "any" else code
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _send_page(cb.message, cb.from_user.id, lang, ctx["origin"], ctx["dest"], truck, 0)


async def _send_page(target, uid, lang, origin, dest, truck, offset):
    loads = await queries.search_loads(origin=origin, destination=dest, truck_type=truck,
                                       limit=PAGE_SIZE + 1, offset=offset)
    has_more = len(loads) > PAGE_SIZE
    loads = loads[:PAGE_SIZE]
    any_word = t(lang, "any")
    tlabel = f" · {t(lang, 'tk_' + truck)}" if truck else ""
    header = f"🔍 {origin or any_word} → {dest or any_word}{tlabel}"
    if not loads:
        _search_ctx.pop(uid, None)
        text = t(lang, "no_more") if offset else format_results([], header, lang)
        await target.answer(text, reply_markup=menu_kb(lang))
        return
    _search_ctx[uid] = {"origin": origin, "dest": dest, "truck": truck, "offset": offset}
    kb = None
    if has_more:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "next"), callback_data="srch_more")]])
    await target.answer(format_results(loads, header, lang), reply_markup=kb)


@router.callback_query(F.data == "srch_more")
async def cb_more(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    await cb.answer()
    ctx = _search_ctx.get(cb.from_user.id)
    if not ctx:
        await cb.message.answer(t(lang, "search_expired"), reply_markup=menu_kb(lang))
        return
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _send_page(cb.message, cb.from_user.id, lang, ctx["origin"], ctx["dest"],
                     ctx.get("truck", ""), ctx["offset"] + PAGE_SIZE)


# ── posting a load ──
@router.message(F.text.in_(variants("btn_post")))
async def on_post(m: Message, state: FSMContext):
    lang = await get_lang(m.from_user.id)
    await state.set_state(Post.filling)
    await state.update_data(idx=0, answers={})
    await m.answer(t(lang, "post_intro") + t(lang, PROMPT_KEY[SEQ[0]]))


@router.message(Post.filling)
async def post_step(m: Message, state: FSMContext):
    lang = await get_lang(m.from_user.id)
    data = await state.get_data()
    idx = data.get("idx", 0)
    answers = data.get("answers", {})
    answers[SEQ[idx]] = _clean(SEQ[idx], (m.text or "").strip())
    idx += 1
    await state.update_data(idx=idx, answers=answers)

    if idx < len(SEQ):
        await m.answer(t(lang, PROMPT_KEY[SEQ[idx]]))
        return

    new_id = await queries.insert_listing(_build_payload(answers), "load", str(m.from_user.id))
    await state.clear()

    from ..db import SessionLocal
    from ..models import Load
    from sqlalchemy import select
    async with SessionLocal() as s:
        load = (await s.execute(select(Load).where(Load.id == new_id))).scalar_one()
    await m.answer(t(lang, "posted_ok") + format_load(load, lang), reply_markup=menu_kb(lang))


def _clean(field: str, text: str):
    if text in ("-", "—"):
        return None if field in ("weight", "price", "phone") else ""
    if field in ("origin", "destination"):
        city, _ = canonical_city(text)
        return city or text
    if field == "weight":
        import re
        mo = re.search(r"\d+(?:[.,]\d+)?", text)
        return float(mo.group().replace(",", ".")) if mo else None
    return text


def _build_payload(answers: dict) -> dict:
    payload = {
        "origin": answers.get("origin", "") or "",
        "destination": answers.get("destination", "") or "",
        "cargo": answers.get("cargo", "") or "",
        "weight": answers.get("weight"),
        "phone": answers.get("phone") or "",
    }
    price_raw = answers.get("price")
    if price_raw:
        amount, currency = _find_price(str(price_raw))
        payload["price"] = amount
        payload["currency"] = currency
    return payload


# ── saved routes + notifications ──
def _sub_label(sub, lang) -> str:
    any_word = t(lang, "any")
    extra = f" · {sub.truck_type}" if sub.truck_type else ""
    return f"{sub.origin or any_word} → {sub.destination or any_word}{extra}"


@router.message(F.text.in_(variants("btn_routes")))
async def on_routes(m: Message, state: FSMContext):
    lang = await get_lang(m.from_user.id)
    await state.clear()
    add_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "routes_add"), callback_data="addroute")]])
    subs = await subscriptions.list_subscriptions(m.from_user.id)
    if not subs:
        await m.answer(t(lang, "routes_none"), reply_markup=add_kb)
        return
    await m.answer(t(lang, "routes_list"))
    for sub in subs:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "routes_del"), callback_data=f"delsub:{sub.id}")]])
        await m.answer(_sub_label(sub, lang), reply_markup=kb)
    await m.answer(t(lang, "routes_more"), reply_markup=add_kb)


@router.callback_query(F.data == "addroute")
async def cb_add_route(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id)
    await state.set_state(Route.origin)
    await cb.message.answer(t(lang, "ask_origin"))
    await cb.answer()


@router.message(Route.origin)
async def route_origin(m: Message, state: FSMContext):
    lang = await get_lang(m.from_user.id)
    await state.update_data(origin=(m.text or "").strip())
    await state.set_state(Route.destination)
    await m.answer(t(lang, "ask_dest"))


@router.message(Route.destination)
async def route_dest(m: Message, state: FSMContext):
    lang = await get_lang(m.from_user.id)
    data = await state.get_data()
    origin = data.get("origin", "")
    origin = "" if origin in ("-", "—") else origin
    dest = (m.text or "").strip()
    dest = "" if dest in ("-", "—", "") else dest
    await state.clear()
    await subscriptions.add_subscription(m.from_user.id, origin, dest)
    any_word = t(lang, "any")
    route = f"{origin or any_word} → {dest or any_word}"
    await m.answer(t(lang, "route_saved", route=route), reply_markup=menu_kb(lang))


@router.callback_query(F.data.startswith("delsub:"))
async def cb_del_route(cb: CallbackQuery):
    lang = await get_lang(cb.from_user.id)
    ok = await subscriptions.delete_subscription(int(cb.data.split(":")[1]), cb.from_user.id)
    await cb.answer(t(lang, "deleted") if ok else t(lang, "not_found"))
    if ok and cb.message:
        try:
            await cb.message.edit_text(t(lang, "deleted_mark"))
        except Exception:
            pass


@router.message()
async def fallback(m: Message):
    lang = await get_lang(m.from_user.id)
    await m.answer(t(lang, "menu_hint"), reply_markup=menu_kb(lang))


async def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is not set. Add it to .env (get it from @BotFather).")
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(UsageMiddleware())
    dp.include_router(router)
    logging.info("Yukdosh bot started (uz/kk/ru).")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
