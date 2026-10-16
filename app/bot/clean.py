"""Remove what would reveal a post's source group or advertise other bots/channels/groups/apps.

Used for the "📄 Asl matn" view and for the comment line on cards."""
import re

_APOS = "['’ʻ`‘]"
# wa.me/+998... is a WhatsApp link whose path IS the phone number: keep the number
_WA_ME = re.compile(r"(?i)(?:https?://)?wa\.me/+")
# bare domains (diip.uz, www.yukon.uz) — not e-mails (a@b.uz) and not decimals (21.5)
_DOMAIN = r"(?<![@\w/.])[a-z0-9-]+\.(?:uz|com|ru|kz|app|io|net|org|me|online|site)\b(?:/\S*)?"
_SOURCE = re.compile(r"(?:https?://|www\.|tg://)\S+|(?<![\w.])t\.me/\S+|(?<![\w.])@\w+|#\w+|"
                     + _DOMAIN, re.I)
# Telegram markdown kept in the scraped text: [text](url) -> text; **bold**, __italic__, ~~strike~~
_MD_LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
_MD_MARK = re.compile(r"\*\*|__|~~|```")
# Whole lines that are ads: other bots/channels/groups/freight apps, "join", "admin", "sent via".
# "bot" only as a separate word: Uzbek places end in -obot (Qo'shrabot, Bekobot, Ashxobot).
# "канал" only as a word: "Канализационные трубы" is real cargo.
# "ilova" (app) only at a word start: surnames end in -ilova (Isroilova, Komilova).
_PROMO_LINE = re.compile(
    rf"(?i)\b(?:bot|бот)(?:{_APOS}?(?:ga|da|ni|dan|imiz\w*|ingiz\w*|га|да|ни|дан))?\b"
    r"|reklam|реклам|obuna|обуна|подпиш|подписыв"
    r"|joylashtiring|жойлаштиринг|guruh|гуруҳ|гурух|\bгрупп"
    r"|\bkanal(?:ga|imiz\w*|da|ni)?\b|\bканал(?:га|имиз\w*|да|ни)?\b"
    r"|\badmin|\bадмин|kirish\s*:|кириш\s*:|ulaning|уланинг|"
    rf"qo{_APOS}?shiling|қўшилинг|присоединя|переходи"
    r"|orqali\s+yuborildi|орқали\s+юборилди|отправлено\s+через|ssilka|силка|ссылк"
    r"|\bilova|\bилова|\bприложени|tarqatil|тарқатил|yuklab\s+ol|юклаб\s+ол|скача"
    r"|play\s*market|app\s*store|\bdiip|\byukon\b|\byukbozor|\bloadme|\blardi"
    r"|" + _DOMAIN
)


def strip_source(text: str) -> str:
    """Drop links, bare domains, @mentions and #hashtags."""
    return _SOURCE.sub("", _WA_ME.sub("", text or ""))


_PHONE = re.compile(r"\d(?:[\s\-()]*\d){8,}")   # 9+ digits = a phone number


def clean_original(text: str) -> str:
    """The original post minus markdown, ad/promo lines, links, @mentions and #hashtags.
    A line with a phone number is never dropped — contact lines often say "Telegram/WhatsApp"."""
    text = _MD_MARK.sub("", _MD_LINK.sub(r"\1", _WA_ME.sub("", text or "")))
    kept = [ln for ln in text.splitlines()
            if _PHONE.search(ln) or not _PROMO_LINE.search(ln)]
    text = strip_source("\n".join(kept))
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
