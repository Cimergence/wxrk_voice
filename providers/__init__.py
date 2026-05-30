"""Provider seam. Selection is 100% env-driven via app.config.Settings.

    from providers import get_llm, get_stt, get_tts

Switching an implementation is changing LLM_PROVIDER / STT_PROVIDER /
TTS_PROVIDER — no code edit anywhere else.
"""
from __future__ import annotations

from app.config import Settings, get_settings
from providers.base import LLMProvider, STTProvider, TTSProvider


def get_llm(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    choice = settings.llm_provider.lower()
    if choice == "gemini":
        from providers.llm import GeminiLLM

        return GeminiLLM(settings)
    if choice in ("stub", "local"):
        from providers.llm import StubLLM

        return StubLLM(settings)
    raise ValueError(f"Unknown LLM_PROVIDER={choice!r} (expected: gemini | stub)")


def get_stt(settings: Settings | None = None) -> STTProvider:
    settings = settings or get_settings()
    choice = settings.stt_provider.lower()
    if choice == "deepgram":
        from providers.stt import DeepgramSTT

        return DeepgramSTT(settings)
    if choice in ("stub", "local", "whisper"):
        from providers.stt import StubSTT

        return StubSTT(settings)
    raise ValueError(f"Unknown STT_PROVIDER={choice!r} (expected: deepgram | stub)")


def get_tts(settings: Settings | None = None) -> TTSProvider:
    settings = settings or get_settings()
    choice = settings.tts_provider.lower()
    if choice == "deepgram":
        from providers.tts import DeepgramTTS

        return DeepgramTTS(settings)
    if choice in ("stub", "local", "piper"):
        from providers.tts import StubTTS

        return StubTTS(settings)
    raise ValueError(f"Unknown TTS_PROVIDER={choice!r} (expected: deepgram | stub)")


__all__ = [
    "LLMProvider",
    "STTProvider",
    "TTSProvider",
    "get_llm",
    "get_stt",
    "get_tts",
]
