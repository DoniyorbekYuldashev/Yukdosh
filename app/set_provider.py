"""Switch the parser provider from the terminal:
    py -m app.set_provider local     (or: openai / gemini / mock)
"""
import asyncio
import sys

from sqlalchemy import select

from .db import init_db, SessionLocal
from .models import Setting


async def main(provider):
    await init_db()
    async with SessionLocal() as s:
        row = (await s.execute(select(Setting).where(Setting.key == "parser_provider"))).scalar_one_or_none()
        if row:
            row.value = provider
        else:
            s.add(Setting(key="parser_provider", value=provider))
        await s.commit()
    print(f"parser_provider set to '{provider}'.")


if __name__ == "__main__":
    prov = sys.argv[1] if len(sys.argv) > 1 else "local"
    asyncio.run(main(prov))
