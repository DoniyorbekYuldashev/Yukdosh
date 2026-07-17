"""Async SQLAlchemy engine/session + startup init (with a tiny SQLite auto-migration)."""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False, future=True)
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
            await _seed_defaults()
            return
        except Exception as exc:  # DB not ready yet / transient race
            last_exc = exc
            await asyncio.sleep(1.5)
    raise last_exc


# New columns we add over time — created on existing SQLite DBs so nothing is lost.
_WANTED_COLUMNS = {
    "groups": {"max_messages": "INTEGER", "hours_back": "INTEGER", "last_msg_id": "INTEGER"},
    "raw_messages": {"parse_attempts": "INTEGER DEFAULT 0"},
    "loads": {"listing_type": "VARCHAR(16) DEFAULT 'load'", "posted_by_tg": "VARCHAR(64) DEFAULT ''", "truck_count": "INTEGER", "comment": "TEXT DEFAULT ''", "source_msg_id": "VARCHAR(64) DEFAULT ''", "notified": "BOOLEAN DEFAULT 0", "poster_username": "VARCHAR(64) DEFAULT ''"},
}


def _ensure_columns(sync_conn) -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return  # for Postgres use real migrations (Alembic)
    from sqlalchemy import inspect, text
    insp = inspect(sync_conn)
    tables = set(insp.get_table_names())
    for table, cols in _WANTED_COLUMNS.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        for col, ddl in cols.items():
            if col not in existing:
                sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


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
        "load_active_hours": "6",           # loads shown to drivers for this many hours
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
