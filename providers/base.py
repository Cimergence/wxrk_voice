"""Abstract provider interfaces. Two impls each (hosted + stub) live alongside."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


class LLMProvider(ABC):
    """Text in, text out. Used by the interview agent, simulator and extractor."""

    name: str = "base"

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.6,
        max_tokens: int | None = None,
    ) -> str:
        ...


class STTProvider(ABC):
    """Speech to text."""

    name: str = "base"

    @abstractmethod
    async def transcribe(self, audio: bytes, *, sample_rate: int = 16000) -> str:
        ...


class TTSProvider(ABC):
    """Text to speech. Returns raw audio bytes."""

    name: str = "base"

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        ...
