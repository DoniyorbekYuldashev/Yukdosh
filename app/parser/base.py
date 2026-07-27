"""Swappable parser interface. parse() returns a LIST of ParsedLoad (0..N per message).

parse_batch() packs SEVERAL messages into ONE API call — essential when the provider limits
requests-per-day (10 messages per call = 10x fewer requests). Providers that don't override
it fall back to one call per message.
"""
from abc import ABC, abstractmethod
from ..schemas import ParsedLoad


class LLMParser(ABC):
    name: str = "base"

    @abstractmethod
    def parse(self, text: str) -> list[ParsedLoad]:
        raise NotImplementedError

    def parse_batch(self, texts: list[str]) -> list[list[ParsedLoad]]:
        return [self.parse(t) for t in texts]
