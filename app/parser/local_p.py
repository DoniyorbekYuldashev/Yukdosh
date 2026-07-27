"""Local-model parser via an OpenAI-compatible server (Ollama / LM Studio / vLLM).
Runs on YOUR GPU -> no API cost, no daily quota.

IMPORTANT: local models are free + unlimited, so we DO NOT batch. One message per call keeps
the task simple ({"loads":[...]}) and matches the few-shot examples exactly -> far better at
splitting multi-direction posts. (Batching only existed to save paid-API requests.)
"""
import json
import re

from .base import LLMParser
from .prompt import build_system_prompt, user_prompt
from .gemini import to_loads
from ..schemas import ParsedLoad
from .. import config

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_THINK = re.compile(r"<think>.*?</think>", re.S)


def _json(text: str):
    """Robustly pull JSON from a local model's reply (strips reasoning + ```json fences)."""
    text = _THINK.sub("", text or "").strip()
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

    def parse(self, text: str) -> list[ParsedLoad]:
        resp = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": user_prompt(text)},
            ],
        )
        return to_loads(_json(resp.choices[0].message.content))

    # NOTE: no parse_batch override on purpose — the base class parses ONE message per call.
