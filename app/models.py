"""Database models. Dynamic config (groups, scrape window, provider, keys) lives
here so it's all editable from the UI at runtime — nothing hardcoded."""
from datetime import datetime, timezone

from sqlalchemy import String, Text, Boolean, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Setting(Base):
    """Key/value app settings, editable from the UI (scrape window, provider, keys)."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Group(Base):
    """A Telegram group/channel to scrape. Managed dynamically from the UI."""
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    link: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # optional per-group scrape overrides; fall back to global settings when None
    max_messages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hours_back: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_msg_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # incremental scrape cursor
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RawMessage(Base):
    """A raw scraped message before parsing."""
    __tablename__ = "raw_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_group: Mapped[str] = mapped_column(String(255), default="")
    source_msg_id: Mapped[str] = mapped_column(String(64), default="")
    sender: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    parse_attempts: Mapped[int] = mapped_column(Integer, default=0)

    load: Mapped["Load"] = relationship(back_populates="raw_message", uselist=False)


class Load(Base):
    """A parsed/structured listing: a load to move, goods for sale, or an empty truck.

    Comes either from scraping (source_group = a Telegram group) or first-party from
    the bot (source_group = 'bot', posted_by_tg = the user's Telegram id).
    """
    __tablename__ = "loads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    is_load: Mapped[bool] = mapped_column(Boolean, default=True)  # True=cargo/goods, False=empty truck
    listing_type: Mapped[str] = mapped_column(String(16), default="load")  # load | goods | truck

    origin_city: Mapped[str] = mapped_column(String(128), default="")
    origin_region: Mapped[str] = mapped_column(String(128), default="")
    destination_city: Mapped[str] = mapped_column(String(128), default="")
    destination_region: Mapped[str] = mapped_column(String(128), default="")

    cargo_type: Mapped[str] = mapped_column(String(128), default="")
    weight_tons: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    volume_m3: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    truck_type: Mapped[str] = mapped_column(String(64), default="")
    truck_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    price_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    price_currency: Mapped[str] = mapped_column(String(8), default="")

    loading_date: Mapped[str] = mapped_column(String(32), default="")
    contact_phone: Mapped[str] = mapped_column(String(64), default="")
    contact_name: Mapped[str] = mapped_column(String(128), default="")

    comment: Mapped[str] = mapped_column(Text, default="")
    language_detected: Mapped[str] = mapped_column(String(16), default="")
    parser_provider: Mapped[str] = mapped_column(String(16), default="")
    dedup_hash: Mapped[str] = mapped_column(String(64), index=True, default="")
    notified: Mapped[bool] = mapped_column(Boolean, default=False)  # pushed to matching drivers?

    source_group: Mapped[str] = mapped_column(String(255), default="")
    source_msg_id: Mapped[str] = mapped_column(String(64), default="")  # original Telegram message id
    posted_by_tg: Mapped[str] = mapped_column(String(64), default="")  # Telegram user id if posted via bot
    poster_username: Mapped[str] = mapped_column(String(64), default="")  # @username of the group poster (scraped)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    raw_message_id: Mapped[int | None] = mapped_column(ForeignKey("raw_messages.id"), nullable=True)
    raw_message: Mapped["RawMessage"] = relationship(back_populates="load")


class Subscription(Base):
    """A driver's saved route: notify them when a matching load appears."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[str] = mapped_column(String(64), index=True)
    origin: Mapped[str] = mapped_column(String(128), default="")       # canonical city or "" = any
    destination: Mapped[str] = mapped_column(String(128), default="")  # canonical city or "" = any
    truck_type: Mapped[str] = mapped_column(String(64), default="")    # optional filter
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BotUser(Base):
    """A person who has used the bot — for usage analytics (count, first/last seen)."""
    __tablename__ = "bot_users"

    tg_user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    first_name: Mapped[str] = mapped_column(String(128), default="")
    language: Mapped[str] = mapped_column(String(8), default="")
    lang: Mapped[str] = mapped_column(String(8), default="")  # language chosen in the bot
    actions: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
