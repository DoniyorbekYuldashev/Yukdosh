"""Remove what would reveal a post's source group or advertise other bots/channels/groups.

Used for the "📄 Asl matn" view and for the comment line on cards."""
import re

_APOS = "['’ʻ`‘]"
_SOURCE = re.compile(r"(?:https?://|www\.)\S+|(?<![\w.])t\.me/\S+|(?<![\w.])@\w+|#\w+")
# Whole lines that are ads: other bots/channels/groups, "join", "admin", "sent via" footers.
# "bot" only as a separate word: Uzbek places end in -obot (Qo'shrabot, Bekobot, Ashxobot).
# "канал" only as a word: "Канализационные трубы" is real cargo.
_PROMO_LINE = re.compile(
    rf"(?i)\b(?:bot|бот)(?:{_APOS}?(?:ga|da|ni|dan|imiz\w*|ingiz\w*|га|да|ни|дан))?\b"
    r"|reklam|реклам|obuna|обуна|подпиш|подписыв"
    r"|joylashtiring|жойлаштиринг|guruh|гуруҳ|гурух|\bгрупп"
    r"|\bkanal(?:ga|imiz\w*|da|ni)?\b|\bканал(?:га|имиз\w*|да|ни)?\b"
    r"|\badmin|\bадмин|kirish\s*:|кириш\s*:|ulaning|уланинг|"
    rf"qo{_APOS}?shiling|қўшилинг|присоединя|переходи"
    r"|orqali\s+yuborildi|орқали\s+юборилди|отправлено\s+через|ssilka|силка|ссылк"
)


def strip_source(text: str) -> str:
    """Drop links, @mentions and #hashtags."""
    return _SOURCE.sub("", text or "")


_PHONE = re.compile(r"\d(?:[\s\-()]*\d){8,}")   # 9+ digits = a phone number


def clean_original(text: str) -> str:
    """The original post minus ad/promo lines, links, @mentions and #hashtags.
    A line with a phone number is never dropped — contact lines often say "Telegram/WhatsApp"."""
    kept = [ln for ln in (text or "").splitlines()
            if _PHONE.search(ln) or not _PROMO_LINE.search(ln)]
    text = strip_source("\n".join(kept))
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
