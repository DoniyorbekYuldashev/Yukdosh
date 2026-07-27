"""Local-model parser via an OpenAI-compatible server (Ollama / LM Studio / vLLM).
Runs on YOUR GPU -> no API cost, no daily quota. Configure with:
    OLLAMA_BASE_URL  (default http://localhost:11434/v1)
    LOCAL_MODEL      (default qwen3:8b)
Then set parser_provider = "local".
"""
import json
import re

from .base import LLMParser
from .prompt import build_system_prompt, user_prompt, batch_user_prompt
from .gemini import to_loads, split_batch
from ..schemas import ParsedLoad
from .. import config

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _json(text: str):
    """Robustly pull JSON out of a local model's reply (handles ```json fences / stray prose)."""
    text = (text or "").strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
    a, b = text.find("{"), text.rfind("}")
    if a != -1 and b > a:
        text = text[a:b + 1]
    return json.loads(text)


class LocalParser(LLMParser):
    name = "local"

    def __init__(self, base_url: str = "", model: str = ""):
        from openai import OpenAI
        self._client = OpenAI(api_key="local", base_url=base_url or config.OLLAMA_BASE_URL)
        self._model = model or config.LOCAL_MODEL
        self._system = build_system_prompt()

    def _call(self, user_content: str):
        resp = self._client.chat.completions.create(
            model=self._model,
            temperature=0,                       # deterministic -> best JSON adherence
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": user_content},
            ],
        )
        return _json(resp.choices[0].message.content)

    def parse(self, text: str) -> list[ParsedLoad]:
        return to_loads(self._call(user_prompt(text)))

    def parse_batch(self, texts: list[str]) -> list[list[ParsedLoad]]:
        if not texts:
            return []
        return split_batch(self._call(batch_user_prompt(texts)), len(texts))
