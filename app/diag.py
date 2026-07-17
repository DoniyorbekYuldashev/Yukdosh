"""Diagnose why loads aren't showing. Tests the ACTUAL configured provider (gemini/openai)
and shows DB state. Run (app can stay running):  py -m app.diag"""
import asyncio
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func

from .db import init_db, SessionLocal
from .models import Load, RawMessage, Setting
from . import config

SAMPLE = "🇧🇾Борисов-🇺🇿Ташкент 🚐тент 📥пиломатериалы 23тн 💰 +998975453270"


async def main():
    await init_db()
    async with SessionLocal() as s:
        async def g(k):
            r = (await s.execute(select(Setting).where(Setting.key == k))).scalar_one_or_none()
            return r.value if r else ""
        provider = await g("parser_provider") or "?"
        gemini_key = await g("gemini_api_key") or config.GEMINI_API_KEY
        openai_key = await g("openai_api_key") or config.OPENAI_API_KEY
        hrs = await g("load_active_hours")
        active_hours = int(hrs) if hrs.isdigit() else 6

        total = (await s.execute(select(func.count()).select_from(Load))).scalar_one()
        scraped = (await s.execute(select(func.count()).select_from(Load).where(Load.source_group != "bot"))).scalar_one()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=active_hours)
        fresh = (await s.execute(select(func.count()).select_from(Load).where(Load.posted_at >= cutoff))).scalar_one()
        rawn = (await s.execute(select(func.count()).select_from(RawMessage))).scalar_one()
        unproc = (await s.execute(select(func.count()).select_from(RawMessage).where(RawMessage.processed == False))).scalar_one()  # noqa: E712

    # effective provider (same logic as the pipeline)
    eff = provider
    if eff in ("", "mock") and gemini_key:
        eff = "gemini"
    elif eff in ("", "mock") and openai_key:
        eff = "openai"

    print("\n=== SETTINGS ===")
    print(f"  provider (setting) : {provider}")
    print(f"  provider (effective): {eff}")
    print(f"  gemini key : {'set' if gemini_key else 'NO'}")
    print(f"  openai key : {'set (' + openai_key[:7] + '…)' if openai_key else 'NO'}")
    print(f"  freshness  : {active_hours}h")
    print("=== DATABASE ===")
    print(f"  loads: {total} (scraped={scraped}, bot={total - scraped}) | fresh<{active_hours}h: {fresh}")
    print(f"  raw:   {rawn} (queued/unparsed={unproc})")

    print(f"\n=== PARSER TEST ({eff}) — real API call ===")
    try:
        if eff == "openai":
            if not openai_key:
                print("  No OpenAI key set."); return
            from .parser.openai_p import OpenAIParser
            p = OpenAIParser(openai_key)
        elif eff == "gemini":
            if not gemini_key:
                print("  No Gemini key set."); return
            from .parser.gemini import GeminiParser
            p = GeminiParser(gemini_key)
            print(f"  gemini model: {p.model_name}")
        else:
            print(f"  provider is '{eff}' — set gemini or openai in Settings."); return
        loads = p.parse(SAMPLE)
        print(f"  ✅ WORKS — parsed {len(loads)} load(s):")
        for L in loads:
            print(f"     {L.origin_city} -> {L.destination_city} | {L.cargo_type} {L.weight_tons}t | {L.contact_phone}")
    except Exception as e:
        print(f"  ❌ FAILED: {e!r}")


if __name__ == "__main__":
    asyncio.run(main())
