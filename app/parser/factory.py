"""Picks the parser provider from the DB settings. Falls back to the offline mock parser
if the real provider isn't configured or its SDK isn't installed."""
from .base import LLMParser
from .mock import MockParser


def get_parser(provider: str, gemini_key: str = "", openai_key: str = "") -> LLMParser:
    provider = (provider or "mock").lower()
    try:
        if provider == "gemini":
            from .gemini import GeminiParser
            return GeminiParser(gemini_key)
        if provider == "openai":
            from .openai_p import OpenAIParser
            return OpenAIParser(openai_key)
    except Exception as exc:
        print(f"[parser] provider '{provider}' unavailable ({exc}); using mock parser")
    return MockParser()
