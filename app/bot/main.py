"""Sarbon24 driver/seller/buyer bot (aiogram v3).

Two-sided:
  • SEARCH — drivers find loads by route (+optional truck type), browse newest loads.
  • POST   — load owners / sellers submit a load, goods-for-sale, or empty truck via a
             guided Q&A. First-party posts save to the same DB and appear in search.

Reads/writes the same DB the scraping+parsing pipeline fills.
Run:  python -m app.bot.main   (needs BOT_TOKEN in .env)
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, F
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
from ..parser.mock import _find_price
from ..parser.normalize import canonical_city
from . import queries, subscriptions
from .formatting import format_results, format_load

logging.basicConfig(level=logging.INFO)
router = Router()

PAGE_SIZE = 5              # loads per page in search
_search_ctx: dict = {}     # user_id -> last search {origin, dest, truck, offset}

# ── menu buttons ──
BTN_POST = "➕ Yuk e'lonini berish"
BTN_SEARCH = "🔍 Yuk qidirish"
BTN_LATEST = "🆕 Yangi yuklar"
BTN_HELP = "ℹ️ Yordam"
BTN_ROUTES = "🔔 Yo'nalishlarim"

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_POST)],
        [KeyboardButton(text=BTN_SEARCH), KeyboardButton(text=BTN_ROUTES)],
        [KeyboardButton(text=BTN_LATEST), KeyboardButton(text=BTN_HELP)],
    ],
    resize_keyboard=True,
)

# ── post-type buttons ──
KIND_LOAD = "📦 Yuk bor (tashish kerak)"
KIND_GOODS = "🛒 Mahsulot sotaman"
KIND_TRUCK = "🚛 Bo'sh mashinam bor"
KIND_CANCEL = "❌ Bekor qilish"

KIND_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=KIND_LOAD)], [KeyboardButton(text=KIND_GOODS)],
              [KeyboardButton(text=KIND_TRUCK)], [KeyboardButton(text=KIND_CANCEL)]],
    resize_keyboard=True,
)

# ── search truck-type picker (inline, optional) ──
_SEARCH_TRUCK_TYPES = [
    ("Tent", "tent"), ("Ref", "ref"), ("Izoterm", "isotherm"),
    ("Bortli", "flatbed"), ("Konteyner", "container"), ("Samosval", "dump"),
    ("Isuzu", "isuzu"), ("Paravoz", "paravoz"),
]


def _truck_inline() -> InlineKeyboardMarkup:
    rows, row = [], []
    for label, val in _SEARCH_TRUCK_TYPES:
        row.append(InlineKeyboardButton(text=label, callback_data=f"st:{val}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔀 Farqi yo'q (hammasi)", callback_data="st:any")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


WELCOME = (
    "Assalomu alaykum! <b>Sarbon24</b> — yuk va mahsulotlarni bir joyda.\n\n"
    "🔎 Yuk qidiring, ➕ o'z e'loningizni bering.\n\n"
    "Quyidagidan tanlang:"
)
HELP = (
    "<b>Sarbon24 yordam</b>\n\n"
    f"{BTN_POST} — yuk, mahsulot yoki bo'sh mashina e'lonini berish\n"
    f"{BTN_SEARCH} — yo'nalish (va mashina turi) bo'yicha yuk qidirish\n"
    f"{BTN_LATEST} — eng yangi yuklar\n"
    f"{BTN_ROUTES} — yo'nalish saqlab, yangi yuklardan xabar oling\n\n"
    "Bekor qilish: /cancel"
)

# ── posting flow ──
SEQ = {
    "load": ["origin", "destination", "cargo", "weight", "price", "phone"],
    "truck": ["origin", "destination", "weight", "price", "phone"],
    "goods": ["cargo", "origin", "weight", "price", "phone"],
}
PROMPT = {
    "origin": "📍 Qayerdan? (shahar)",
    "destination": "📍 Qayerga? (shahar)",
    "cargo_load": "📦 Yuk nomi? (masalan: paxta, meva)",
    "cargo_goods": "🛒 Mahsulot nomi? (masalan: pomidor 1-nav)",
    "weight": "⚖️ Necha tonna? ('-' bilmasangiz)",
    "price": "💰 Narxi? (masalan: 45 mln so'm, yoki '-')",
    "phone": "📞 Telefon raqamingiz? ('-' → Telegram orqali)",
}


class Search(StatesGroup):
    origin = State()
    destination = State()


class Post(StatesGroup):
    filling = State()


class Route(StatesGroup):
    origin = State()
    destination = State()


def _prompt_for(field: str, kind: str) -> str:
    if field == "cargo":
        return PROMPT["cargo_goods"] if kind == "goods" else PROMPT["cargo_load"]
    return PROMPT[field]


# ── basic commands ──
@router.message(Command("start"))
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(WELCOME, reply_markup=MENU)


@router.message(Command("cancel"))
async def cmd_cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Bekor qilindi.", reply_markup=MENU)


@router.message(F.text == BTN_HELP)
async def on_help(m: Message):
    await m.answer(HELP, reply_markup=MENU)


# ── browse / search ──
@router.message(F.text == BTN_LATEST)
async def on_latest(m: Message):
    await m.answer(format_results(await queries.latest_loads(10), "🆕 Eng yangi yuklar"), reply_markup=MENU)


@router.message(F.text == BTN_SEARCH)
async def on_search(m: Message, state: FSMContext):
    await state.set_state(Search.origin)
    await m.answer("Qayerdan? (masalan: Toshkent, Qashqadaryo, Rossiya)")


@router.message(Search.origin)
async def search_origin(m: Message, state: FSMContext):
    await state.update_data(origin=(m.text or "").strip())
    await state.set_state(Search.destination)
    await m.answer("Qayerga? (farqi yo'q bo'lsa '-')")


@router.message(Search.destination)
async def search_do(m: Message, state: FSMContext):
    data = await state.get_data()
    origin = data.get("origin", "")
    dest = (m.text or "").strip()
    origin = "" if origin in ("-", "—") else origin
    dest = "" if dest in ("-", "—", "") else dest
    await state.clear()
    _search_ctx[m.from_user.id] = {"origin": origin, "dest": dest, "truck": "", "offset": 0}
    await m.answer("🚚 Mashina turi? (ixtiyoriy — tanlamasangiz hammasi)", reply_markup=_truck_inline())


@router.callback_query(F.data.startswith("st:"))
async def cb_search_truck(cb: CallbackQuery):
    await cb.answer()
    ctx = _search_ctx.get(cb.from_user.id)
    if not ctx:
        await cb.message.answer("Qidiruv eskirgan. Qaytadan qidiring 🔍", reply_markup=MENU)
        return
    t = cb.data.split(":", 1)[1]
    truck = "" if t == "any" else t
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _send_search_page(cb.message, cb.from_user.id, ctx["origin"], ctx["dest"], truck, 0)


async def _send_search_page(target, uid, origin, dest, truck, offset):
    loads = await queries.search_loads(origin=origin, destination=dest, truck_type=truck,
                                       limit=PAGE_SIZE + 1, offset=offset)
    has_more = len(loads) > PAGE_SIZE
    loads = loads[:PAGE_SIZE]
    tlabel = f" · {truck}" if truck else ""
    header = f"🔍 {origin or 'hamma'} → {dest or 'hamma'}{tlabel}"
    if not loads:
        _search_ctx.pop(uid, None)
        await target.answer("Boshqa yuk yo\'q." if offset else format_results([], header), reply_markup=MENU)
        return
    _search_ctx[uid] = {"origin": origin, "dest": dest, "truck": truck, "offset": offset}
    kb = None
    if has_more:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Keyingi ➡️", callback_data="srch_more")]])
    await target.answer(format_results(loads, header), reply_markup=kb)


@router.callback_query(F.data == "srch_more")
async def cb_more(cb: CallbackQuery):
    await cb.answer()
    ctx = _search_ctx.get(cb.from_user.id)
    if not ctx:
        await cb.message.answer("Qidiruv eskirgan. Qaytadan qidiring 🔍", reply_markup=MENU)
        return
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await _send_search_page(cb.message, cb.from_user.id, ctx["origin"], ctx["dest"],
                            ctx.get("truck", ""), ctx["offset"] + PAGE_SIZE)


# ── posting ──
@router.message(F.text == BTN_POST)
async def on_post(m: Message, state: FSMContext):
    await state.set_state(Post.filling)
    await state.update_data(kind="load", idx=0, answers={})
    await m.answer("📦 Yuk e'loni.\n\n" + _prompt_for(SEQ["load"][0], "load"))


@router.message(Post.filling)
async def post_step(m: Message, state: FSMContext):
    text = (m.text or "").strip()
    if text == KIND_CANCEL:
        await state.clear()
        await m.answer("Bekor qilindi.", reply_markup=MENU)
        return

    data = await state.get_data()
    kind = data.get("kind")

    if not kind:
        kind = {KIND_LOAD: "load", KIND_GOODS: "goods", KIND_TRUCK: "truck"}.get(text)
        if not kind:
            await m.answer("Iltimos, tugmalardan birini tanlang.", reply_markup=KIND_KB)
            return
        await state.update_data(kind=kind, idx=0, answers={})
        first = SEQ[kind][0]
        await m.answer(_prompt_for(first, kind))
        return

    idx = data.get("idx", 0)
    answers = data.get("answers", {})
    seq = SEQ[kind]
    field = seq[idx]
    answers[field] = _clean(field, text)
    idx += 1
    await state.update_data(idx=idx, answers=answers)

    if idx < len(seq):
        await m.answer(_prompt_for(seq[idx], kind))
        return

    payload = _build_payload(answers)
    new_id = await queries.insert_listing(payload, kind, str(m.from_user.id))
    await state.clear()

    from ..db import SessionLocal
    from ..models import Load
    from sqlalchemy import select
    async with SessionLocal() as s:
        load = (await s.execute(select(Load).where(Load.id == new_id))).scalar_one()
    await m.answer("✅ E'loningiz joylandi:\n\n" + format_load(load), reply_markup=MENU)


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
def _sub_label(sub) -> str:
    t = f" · {sub.truck_type}" if sub.truck_type else ""
    return f"{sub.origin or 'hamma'} → {sub.destination or 'hamma'}{t}"


_ADD_KB = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Yo'nalish qo'shish", callback_data="addroute")]])


@router.message(F.text == BTN_ROUTES)
async def on_routes(m: Message, state: FSMContext):
    await state.clear()
    subs = await subscriptions.list_subscriptions(m.from_user.id)
    if not subs:
        await m.answer("Sizda saqlangan yo'nalish yo'q.\n\nYo'nalish saqlang — o'sha yo'nalishda yangi yuk chiqishi bilan xabar beraman.",
                       reply_markup=_ADD_KB)
        return
    await m.answer("🔔 <b>Saqlangan yo'nalishlaringiz:</b>")
    for sub in subs:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delsub:{sub.id}")]])
        await m.answer(_sub_label(sub), reply_markup=kb)
    await m.answer("Yana qo'shasizmi?", reply_markup=_ADD_KB)


@router.callback_query(F.data == "addroute")
async def cb_add_route(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Route.origin)
    await cb.message.answer("Qayerdan? (masalan: Toshkent)")
    await cb.answer()


@router.message(Route.origin)
async def route_origin(m: Message, state: FSMContext):
    await state.update_data(origin=(m.text or "").strip())
    await state.set_state(Route.destination)
    await m.answer("Qayerga? (farqi yo'q bo'lsa '-')")


@router.message(Route.destination)
async def route_dest(m: Message, state: FSMContext):
    data = await state.get_data()
    origin = data.get("origin", "")
    origin = "" if origin in ("-", "—") else origin
    dest = (m.text or "").strip()
    dest = "" if dest in ("-", "—", "") else dest
    await state.clear()
    await subscriptions.add_subscription(m.from_user.id, origin, dest)
    await m.answer(f"✅ Saqlandi: <b>{origin or 'hamma'} → {dest or 'hamma'}</b>\nShu yo'nalishda yangi yuk chiqsa, darhol xabar beraman.", reply_markup=MENU)


@router.callback_query(F.data.startswith("delsub:"))
async def cb_del_route(cb: CallbackQuery):
    ok = await subscriptions.delete_subscription(int(cb.data.split(":")[1]), cb.from_user.id)
    await cb.answer("O'chirildi" if ok else "Topilmadi")
    if ok and cb.message:
        try:
            await cb.message.edit_text("🗑 O'chirildi")
        except Exception:
            pass


@router.message()
async def fallback(m: Message):
    await m.answer("Menyudan tanlang 👇", reply_markup=MENU)


async def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is not set. Add it to .env (get it from @BotFather).")
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logging.info("Sarbon24 bot started.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
