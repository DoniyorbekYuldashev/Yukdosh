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
            temperature=0,  # extraction, not creativity: same post -> same answer
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": user_prompt(text)},
            ],
        )
        return to_loads(json.loads(resp.choices[0].message.content))

    def parse_batch(self, texts: list[str]) -> list[list[ParsedLoad]]:
        if not texts:
            return []
        try:
            return self._parse_batch(texts)
        except ValueError:            # broken/cut-off JSON (json.JSONDecodeError is a ValueError)
            if len(texts) == 1:
                raise
            # one message can send the model into a repetition loop: retry one by one so it
            # can't take the other messages down with it
            out = []
            for t in texts:
                try:
                    out.append(self._parse_batch([t])[0])
                except ValueError as exc:
                    print(f"[parser] skipped one message: {exc}")
                    out.append([])
            return out

    def _parse_batch(self, texts: list[str]) -> list[list[ParsedLoad]]:
        resp = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            temperature=0,  # extraction, not creativity: same post -> same answer
            max_tokens=6000,  # a normal batch needs ~1-2k; stops a runaway repetition loop early
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": batch_user_prompt(texts)},
            ],
        )
        return split_batch(json.loads(resp.choices[0].message.content), len(texts))
