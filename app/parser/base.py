"""Swappable parser interface. parse() returns a LIST of ParsedLoad (0..N per message)."""
from abc import ABC, abstractmethod
from ..schemas import ParsedLoad


class LLMParser(ABC):
    name: str = "base"

    @abstractmethod
    def parse(self, text: str) -> list[ParsedLoad]:
        raise NotImplementedError
