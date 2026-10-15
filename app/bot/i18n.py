"""Translations for the driver bot: Uzbek (uz), Kazakh (kk), Russian (ru).

Every user-facing string lives here. Use t(lang, key, **fmt) everywhere — never hardcode
text in handlers, or one language ends up leaking into another.
"""
from .. db import SessionLocal
from .. models import BotUser

DEFAULT_LANG = "uz"

LANG_NAMES = {"uz": "🇺🇿 O'zbekcha", "kk": "🇰🇿 Қазақша", "ru": "🇷🇺 Русский"}

TEXTS: dict[str, dict[str, str]] = {
    "uz": {
        "btn_post": "➕ Yuk e'lonini berish",
        "btn_search": "🔍 Yuk qidirish",
        "btn_latest": "🆕 Yangi yuklar",
        "btn_routes": "🔔 Yo'nalishlarim",
        "btn_help": "ℹ️ Yordam",
        "welcome": "Assalomu alaykum! <b>Yukdosh</b> — yuk va haydovchilarni bog'laydi.\n\nQuyidagidan tanlang:",
        "help": ("<b>Yukdosh yordam</b>\n\n"
                 "➕ Yuk e'lonini berish — o'z yukingizni joylang\n"
                 "🔍 Yuk qidirish — yo'nalish va mashina turi bo'yicha toping\n"
                 "🆕 Yangi yuklar — eng so'nggi yuklar\n"
                 "🔔 Yo'nalishlarim — yo'nalish saqlab, yangi yukdan xabar oling\n"
                 "🌐 /lang — tilni o'zgartirish\n\n"
                 "Bekor qilish: /cancel"),
        "choose_lang": "Tilni tanlang:",
        "lang_set": "✅ Til o'zgartirildi.",
        "cancelled": "Bekor qilindi.",
        "ask_origin": "Qayerdan? (masalan: Toshkent)",
        "ask_dest": "Qayerga? (farqi yo'q bo'lsa '-')",
        "ask_truck": "🚚 Mashina turi? (ixtiyoriy — tanlamasangiz hammasi)",
        "truck_any": "🔀 Farqi yo'q (hammasi)",
        "search_expired": "Qidiruv eskirgan. Qaytadan qidiring 🔍",
        "no_more": "Boshqa yuk yo'q.",
        "next": "Keyingi ➡️",
        "post_intro": "📦 Yuk e'loni.\n\n",
        "choose_button": "Iltimos, tugmalardan birini tanlang.",
        "posted_ok": "✅ E'loningiz joylandi:\n\n",
        "menu_hint": "Menyudan tanlang 👇",
        "routes_none": "Sizda saqlangan yo'nalish yo'q.\n\nYo'nalish saqlang — o'sha yo'nalishda yangi yuk chiqishi bilan xabar beraman.",
        "routes_add": "➕ Yo'nalish qo'shish",
        "routes_list": "🔔 <b>Saqlangan yo'nalishlaringiz:</b>",
        "routes_del": "🗑 O'chirish",
        "routes_more": "Yana qo'shasizmi?",
        "deleted": "O'chirildi",
        "not_found": "Topilmadi",
        "deleted_mark": "🗑 O'chirildi",
        "route_saved": "✅ Saqlandi: <b>{route}</b>\nShu yo'nalishda yangi yuk chiqsa, darhol xabar beraman.",
        "any": "hamma",
        "latest_title": "🆕 Eng yangi yuklar",
        "group_post_footer": "🔍 Ko'proq yuklar va yo'nalishingiz bo'yicha qidiruv: {bot}",
        "nothing_found": "Hech narsa topilmadi. Keyinroq urinib ko'ring.",
        "p_origin": "📍 Qayerdan? (shahar)",
        "p_dest": "📍 Qayerga? (shahar)",
        "p_cargo": "📦 Yuk nomi? (masalan: paxta, meva)",
        "p_weight": "⚖️ Necha tonna? ('-' bilmasangiz)",
        "p_price": "💰 Narxi? (masalan: 45 mln so'm, yoki '-')",
        "p_phone": "📞 Telefon raqamingiz? ('-' → Telegram orqali)",
        "notify_new": "🔔 <b>Yangi yuk sizning yo'nalishingizda!</b>\n\n",
        "price_none": "kelishiladi",
        "today": "Bugun",
        "yesterday": "Kecha",
        "raw_btn": "📄 Asl matn",
        "raw_title": "📄 <b>E'lonning asl matni</b>",
        "raw_hint": "📄 N — e'lonning asl matni",
        "via_bot": "Yukdosh orqali",
        "goods": "Mahsulot",
        "tk_tent": "Tent", "tk_ref": "Refrijerator", "tk_isotherm": "Izoterm",
        "tk_flatbed": "Bortli", "tk_container": "Konteyner", "tk_dump": "Samosval",
        "tk_isuzu": "Isuzu", "tk_paravoz": "Paravoz", "tk_labo": "Labo", "tk_other": "Boshqa",
    },
    "kk": {
        "btn_post": "➕ Жүк жариялау",
        "btn_search": "🔍 Жүк іздеу",
        "btn_latest": "🆕 Жаңа жүктер",
        "btn_routes": "🔔 Менің бағыттарым",
        "btn_help": "ℹ️ Көмек",
        "welcome": "Сәлеметсіз бе! <b>Yukdosh</b> — жүк пен жүргізушіні байланыстырады.\n\nТөмендегіден таңдаңыз:",
        "help": ("<b>Yukdosh көмек</b>\n\n"
                 "➕ Жүк жариялау — өз жүгіңізді жариялаңыз\n"
                 "🔍 Жүк іздеу — бағыт және көлік түрі бойынша табыңыз\n"
                 "🆕 Жаңа жүктер — соңғы жүктер\n"
                 "🔔 Менің бағыттарым — бағыт сақтап, жаңа жүктен хабар алыңыз\n"
                 "🌐 /lang — тілді өзгерту\n\n"
                 "Болдырмау: /cancel"),
        "choose_lang": "Тілді таңдаңыз:",
        "lang_set": "✅ Тіл өзгертілді.",
        "cancelled": "Болдырылмады.",
        "ask_origin": "Қайдан? (мысалы: Алматы)",
        "ask_dest": "Қайда? (маңызды емес болса '-')",
        "ask_truck": "🚚 Көлік түрі? (міндетті емес — таңдамасаңыз барлығы)",
        "truck_any": "🔀 Маңызды емес (барлығы)",
        "search_expired": "Іздеу ескірген. Қайта іздеңіз 🔍",
        "no_more": "Басқа жүк жоқ.",
        "next": "Келесі ➡️",
        "post_intro": "📦 Жүк жарнамасы.\n\n",
        "choose_button": "Түймелердің бірін таңдаңыз.",
        "posted_ok": "✅ Жарнамаңыз орналастырылды:\n\n",
        "menu_hint": "Мәзірден таңдаңыз 👇",
        "routes_none": "Сізде сақталған бағыт жоқ.\n\nБағыт сақтаңыз — сол бағытта жаңа жүк шыққанда хабарлаймын.",
        "routes_add": "➕ Бағыт қосу",
        "routes_list": "🔔 <b>Сақталған бағыттарыңыз:</b>",
        "routes_del": "🗑 Өшіру",
        "routes_more": "Тағы қосасыз ба?",
        "deleted": "Өшірілді",
        "not_found": "Табылмады",
        "deleted_mark": "🗑 Өшірілді",
        "route_saved": "✅ Сақталды: <b>{route}</b>\nОсы бағытта жаңа жүк шықса, бірден хабарлаймын.",
        "any": "барлығы",
        "latest_title": "🆕 Соңғы жүктер",
        "group_post_footer": "🔍 Көбірек жүк және бағытыңыз бойынша іздеу: {bot}",
        "nothing_found": "Ештеңе табылмады. Кейінірек қайталап көріңіз.",
        "p_origin": "📍 Қайдан? (қала)",
        "p_dest": "📍 Қайда? (қала)",
        "p_cargo": "📦 Жүк атауы? (мысалы: мақта, жеміс)",
        "p_weight": "⚖️ Неше тонна? (білмесеңіз '-')",
        "p_price": "💰 Бағасы? (мысалы: 500 мың теңге, немесе '-')",
        "p_phone": "📞 Телефон нөміріңіз? ('-' → Telegram арқылы)",
        "notify_new": "🔔 <b>Сіздің бағытыңызда жаңа жүк!</b>\n\n",
        "price_none": "келісіледі",
        "today": "Бүгін",
        "yesterday": "Кеше",
        "raw_btn": "📄 Түпнұсқа мәтін",
        "raw_title": "📄 <b>Жарнаманың түпнұсқа мәтіні</b>",
        "raw_hint": "📄 N — жарнаманың түпнұсқа мәтіні",
        "via_bot": "Yukdosh арқылы",
        "goods": "Тауар",
        "tk_tent": "Тент", "tk_ref": "Рефрижератор", "tk_isotherm": "Изотерм",
        "tk_flatbed": "Бортты", "tk_container": "Контейнер", "tk_dump": "Самосвал",
        "tk_isuzu": "Isuzu", "tk_paravoz": "Автопойыз", "tk_labo": "Labo", "tk_other": "Басқа",
    },
    "ru": {
        "btn_post": "➕ Разместить груз",
        "btn_search": "🔍 Поиск груза",
        "btn_latest": "🆕 Новые грузы",
        "btn_routes": "🔔 Мои маршруты",
        "btn_help": "ℹ️ Помощь",
        "welcome": "Здравствуйте! <b>Yukdosh</b> — связывает грузы и водителей.\n\nВыберите:",
        "help": ("<b>Yukdosh помощь</b>\n\n"
                 "➕ Разместить груз — опубликуйте свой груз\n"
                 "🔍 Поиск груза — найдите по маршруту и типу машины\n"
                 "🆕 Новые грузы — последние грузы\n"
                 "🔔 Мои маршруты — сохраните маршрут и получайте уведомления\n"
                 "🌐 /lang — сменить язык\n\n"
                 "Отмена: /cancel"),
        "choose_lang": "Выберите язык:",
        "lang_set": "✅ Язык изменён.",
        "cancelled": "Отменено.",
        "ask_origin": "Откуда? (например: Ташкент)",
        "ask_dest": "Куда? (если не важно — '-')",
        "ask_truck": "🚚 Тип машины? (необязательно — если не выбрать, покажем все)",
        "truck_any": "🔀 Не важно (все)",
        "search_expired": "Поиск устарел. Поищите заново 🔍",
        "no_more": "Больше грузов нет.",
        "next": "Далее ➡️",
        "post_intro": "📦 Объявление о грузе.\n\n",
        "choose_button": "Пожалуйста, выберите одну из кнопок.",
        "posted_ok": "✅ Ваше объявление размещено:\n\n",
        "menu_hint": "Выберите в меню 👇",
        "routes_none": "У вас нет сохранённых маршрутов.\n\nСохраните маршрут — и я сообщу, как только появится груз.",
        "routes_add": "➕ Добавить маршрут",
        "routes_list": "🔔 <b>Ваши сохранённые маршруты:</b>",
        "routes_del": "🗑 Удалить",
        "routes_more": "Добавить ещё?",
        "deleted": "Удалено",
        "not_found": "Не найдено",
        "deleted_mark": "🗑 Удалено",
        "route_saved": "✅ Сохранено: <b>{route}</b>\nКак только появится груз на этом маршруте — сразу сообщу.",
        "any": "все",
        "latest_title": "🆕 Последние грузы",
        "group_post_footer": "🔍 Больше грузов и поиск по вашему маршруту: {bot}",
        "nothing_found": "Ничего не найдено. Попробуйте позже.",
        "p_origin": "📍 Откуда? (город)",
        "p_dest": "📍 Куда? (город)",
        "p_cargo": "📦 Название груза? (например: хлопок, фрукты)",
        "p_weight": "⚖️ Сколько тонн? (если не знаете — '-')",
        "p_price": "💰 Цена? (например: 45 млн сум, или '-')",
        "p_phone": "📞 Ваш номер телефона? ('-' → через Telegram)",
        "notify_new": "🔔 <b>Новый груз на вашем маршруте!</b>\n\n",
        "price_none": "договорная",
        "today": "Сегодня",
        "yesterday": "Вчера",
        "raw_btn": "📄 Исходный текст",
        "raw_title": "📄 <b>Исходный текст объявления</b>",
        "raw_hint": "📄 N — исходный текст объявления",
        "via_bot": "через Yukdosh",
        "goods": "Товар",
        "tk_tent": "Тент", "tk_ref": "Рефрижератор", "tk_isotherm": "Изотерм",
        "tk_flatbed": "Бортовой", "tk_container": "Контейнер", "tk_dump": "Самосвал",
        "tk_isuzu": "Isuzu", "tk_paravoz": "Автопоезд", "tk_labo": "Labo", "tk_other": "Другое",
    },
}


def t(lang: str, key: str, **fmt) -> str:
    """Translated string, falling back to Uzbek if a key/lang is missing."""
    table = TEXTS.get(lang) or TEXTS[DEFAULT_LANG]
    s = table.get(key) or TEXTS[DEFAULT_LANG].get(key, key)
    return s.format(**fmt) if fmt else s


def variants(key: str) -> set[str]:
    """The same button text in EVERY language — so one handler matches all of them."""
    return {TEXTS[l][key] for l in TEXTS if key in TEXTS[l]}


# ── per-user language storage (cached) ─────────────────────────────────────────
_cache: dict[str, str] = {}


async def get_lang(user_id) -> str:
    uid = str(user_id)
    if uid in _cache:
        return _cache[uid]
    async with SessionLocal() as s:
        row = await s.get(BotUser, uid)
    lang = (getattr(row, "lang", "") or "") if row else ""
    if lang in TEXTS:
        _cache[uid] = lang
        return lang
    return DEFAULT_LANG


async def set_lang(user_id, lang: str) -> None:
    uid = str(user_id)
    if lang not in TEXTS:
        lang = DEFAULT_LANG
    async with SessionLocal() as s:
        row = await s.get(BotUser, uid)
        if row:
            row.lang = lang
        else:
            s.add(BotUser(tg_user_id=uid, lang=lang))
        await s.commit()
    _cache[uid] = lang
