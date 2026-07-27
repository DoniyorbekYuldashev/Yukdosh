"""OpenAI parser (gpt-4o-mini) — reliable, cheap (~$0.30 to parse ~800 messages), no free-tier
quota games. Key from https://platform.openai.com/api-keys"""
import json

from .base import LLMParser
from .prompt import build_system_prompt, user_prompt, batch_user_prompt
from .gemini import to_loads, split_batch
from ..schemas import ParsedLoad


class OpenAIParser(LLMParser):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._system = build_system_prompt()

    def parse(self, text: str) -> list[ParsedLoad]:
        resp = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": user_prompt(text)},
            ],
        )
        return to_loads(json.loads(resp.choices[0].message.content))

    def parse_batch(self, texts: list[str]) -> list[list[ParsedLoad]]:
        if not texts:
            return []
        resp = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": batch_user_prompt(texts)},
            ],
        )
        return split_batch(json.loads(resp.choices[0].message.content), len(texts))
