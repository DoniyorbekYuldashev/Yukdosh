"""Async SQLAlchemy engine/session + startup init (with a tiny SQLite auto-migration)."""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


_IS_SQLITE = DATABASE_URL.startswith("sqlite")
# SQLite allows one writer at a time; web+bot+scheduler all write. WAL mode lets readers and a
# writer work concurrently, and busy_timeout makes writers WAIT instead of failing with
# "database is locked". Postgres needs none of this.
# Postgres: 3 processes share a hosted pooler with few slots, and it drops idle connections —
# keep pools small and test each connection before use.
engine = create_async_engine(
    DATABASE_URL, echo=False, future=True,
    **({"connect_args": {"timeout": 30}} if _IS_SQLITE else
       {"pool_size": 3, "max_overflow": 2, "pool_pre_ping": True, "pool_recycle": 1800}),
)

if _IS_SQLITE:
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    # Import models so they register on Base.metadata, then create tables.
    # Retries so services can start before Postgres is fully ready (and to tolerate
    # concurrent CREATE-IF-NOT-EXISTS across web/bot/scheduler).
    import asyncio
    from . import models  # noqa: F401
    last_exc = None
    for attempt in range(20):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.run_sync(_ensure_columns)
                await conn.run_sync(_ensure_indexes)
            await _seed_defaults()
            return
        except Exception as exc:  # DB not ready yet / transient race
            last_exc = exc
            await asyncio.sleep(1.5)
    raise last_exc


# New columns we add over time — created on existing SQLite DBs so nothing is lost.
_WANTED_COLUMNS = {
    "groups": {"max_messages": "INTEGER", "hours_back": "INTEGER", "last_msg_id": "INTEGER"},
    "raw_messages": {"parse_attempts": "INTEGER DEFAULT 0", "text_hash": "VARCHAR(32) DEFAULT ''"},
    "bot_users": {"lang": "VARCHAR(8) DEFAULT ''"},
    "loads": {"listing_type": "VARCHAR(16) DEFAULT 'load'", "posted_by_tg": "VARCHAR(64) DEFAULT ''", "truck_count": "INTEGER", "comment": "TEXT DEFAULT ''", "source_msg_id": "VARCHAR(64) DEFAULT ''", "notified": "BOOLEAN DEFAULT 0", "poster_username": "VARCHAR(64) DEFAULT ''", "advance": "VARCHAR(32) DEFAULT ''"},
}


def _ensure_columns(sync_conn) -> None:
    """Add newly-introduced columns to existing tables. Works on SQLite AND Postgres."""
    from sqlalchemy import inspect, text
    insp = inspect(sync_conn)
    tables = set(insp.get_table_names())
    is_sqlite = DATABASE_URL.startswith("sqlite")
    for table, cols in _WANTED_COLUMNS.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        for col, ddl in cols.items():
            if col in existing:
                continue
            if not is_sqlite:  # Postgres wants a real boolean literal
                ddl = ddl.replace("BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE")
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


# create_all only builds indexes for NEW tables — existing DBs get them here.
_WANTED_INDEXES = {"ix_loads_posted_at": "loads (posted_at)",
                   "ix_raw_messages_text_hash": "raw_messages (text_hash)"}


def _ensure_indexes(sync_conn) -> None:
    from sqlalchemy import text
    for name, target in _WANTED_INDEXES.items():
        sync_conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {target}"))


async def _seed_defaults() -> None:
    """Seed default settings and one example group on first run."""
    from .models import Setting, Group
    from sqlalchemy import select, func

    defaults = {
        "scrape_max_messages": "50",   # global default: latest messages per group
        "scrape_hours_back": "24",     # global default: time window in hours
        "parser_provider": "gemini",   # gemini | mock
        "gemini_api_key": "",
        "openai_api_key": "",
        "scheduler_enabled": "false",       # auto-run the pipeline on a timer
        "scheduler_interval_minutes": "10", # how often to scrape
        "load_active_hours": "12",          # loads shown to drivers for this many hours
        "load_retention_days": "5",         # loads + raw messages deleted after this (0 = keep)
        "card_source_mode": "original",     # bot cards: original | link | both | none
    }
    async with SessionLocal() as s:
        existing = {
            row.key for row in (await s.execute(select(Setting))).scalars().all()
        }
        for k, v in defaults.items():
            if k not in existing:
                s.add(Setting(key=k, value=v))

        count = (await s.execute(select(func.count()).select_from(Group))).scalar_one()
        if count == 0:
            s.add(Group(
                link="https://t.me/example_yuk_group",
                title="Example load group (edit me in Settings)",
                enabled=True,
            ))
        await s.commit()
