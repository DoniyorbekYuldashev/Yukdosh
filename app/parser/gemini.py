"""Gemini parser. Auto-resolves a working flash model from your account, so it keeps working
even when Google renames models. Free key: https://aistudio.google.com/app/apikey"""
import json

from .base import LLMParser
from .prompt import build_system_prompt, user_prompt, batch_user_prompt
from .normalize import canonical_city, canonical_currency, canonicalize_trucks, TRUCK_ALIASES
from ..schemas import ParsedLoad


def _resolve_model(genai, preferred: str) -> str:
    """Return a model available to THIS key that supports generateContent. Prefer the
    requested one, else the newest 'flash' model."""
    try:
        avail = [m.name.split("/")[-1] for m in genai.list_models()
                 if "generateContent" in getattr(m, "supported_generation_methods", [])]
    except Exception:
        return preferred
    if not avail:
        return preferred
    if preferred in avail:
        return preferred
    flash = [n for n in avail if "flash" in n and "lite" not in n and "8b" not in n]
    anyflash = [n for n in avail if "flash" in n]
    for pool in (flash, anyflash, avail):
        if pool:
            return sorted(pool)[-1]  # newest-ish
    return preferred


class GeminiParser(LLMParser):
    name = "gemini"

    def __init__(self, api_key: str, model: str = ""):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        import google.generativeai as genai
        from .. import config
        genai.configure(api_key=api_key)
        self.model_name = _resolve_model(genai, model or config.GEMINI_MODEL)
        self._model = genai.GenerativeModel(
            self.model_name, system_instruction=build_system_prompt(),
            generation_config={"response_mime_type": "application/json"})

    def parse(self, text: str) -> list[ParsedLoad]:
        resp = self._model.generate_content(user_prompt(text))
        return to_loads(json.loads(resp.text))

    def parse_batch(self, texts: list[str]) -> list[list[ParsedLoad]]:
        if not texts:
            return []
        resp = self._model.generate_content(batch_user_prompt(texts))
        return split_batch(json.loads(resp.text), len(texts))


def _to_parsed_load(data: dict) -> ParsedLoad:
    load = ParsedLoad(**{k: data.get(k) for k in ParsedLoad.model_fields if data.get(k) is not None})
    oc, orr = canonical_city(load.origin_city)
    dc, drr = canonical_city(load.destination_city)
    load.origin_city, load.origin_region = oc, orr or load.origin_region
    load.destination_city, load.destination_region = dc, drr or load.destination_region
    # safeguard: a truck word mistakenly placed in cargo_type -> move it to truck_type
    if load.cargo_type and load.cargo_type.strip().lower() in TRUCK_ALIASES:
        if not load.truck_type:
            load.truck_type = TRUCK_ALIASES[load.cargo_type.strip().lower()]
        load.cargo_type = ""
    load.truck_type = canonicalize_trucks(load.truck_type)
    load.price_currency = canonical_currency(load.price_currency) if load.price_currency else ""
    return load


def to_loads(data) -> list[ParsedLoad]:
    if isinstance(data, dict) and "loads" in data:
        items = data["loads"]
    elif isinstance(data, list):
        items = data
    else:
        items = [data]
    out = []
    for it in items or []:
        if isinstance(it, dict):
            try:
                out.append(_to_parsed_load(it))
            except Exception as exc:
                print(f"[parser] skipped a load ({exc})")
    return out


def split_batch(data, n: int) -> list[list[ParsedLoad]]:
    """Map a batched {"results":[{"i":1,"loads":[...]}]} reply back onto the input order."""
    out: list[list[ParsedLoad]] = [[] for _ in range(n)]
    items = data.get("results") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("batch reply missing 'results'")
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            i = int(it.get("i", 0))
        except (TypeError, ValueError):
            continue
        if 1 <= i <= n:
            out[i - 1] = to_loads({"loads": it.get("loads") or []})
    return out
