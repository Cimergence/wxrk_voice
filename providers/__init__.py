"""Provider seam. Selection is 100% env-driven via app.config.Settings.

    from providers import get_llm, get_stt, get_tts

Switching an implementation is changing LLM_PROVIDER / STT_PROVIDER /
TTS_PROVIDER — no code edit anywhere else.
"""
from __future__ import annotations

from typing import Sequence

from app.config import Settings, get_settings
from providers.base import ChatMessage, LLMProvider, STTProvider, TTSProvider


class MeteredLLM(LLMProvider):
    """Wraps any LLM, recording estimated input/output tokens into a RoleMeter so
    the run can be priced from the resolved catalog model. Execution is delegated
    unchanged to the inner provider."""

    def __init__(self, inner: LLMProvider, meter) -> None:
        self.inner = inner
        self.meter = meter
        self.name = f"metered:{inner.name}"

    async def complete(
        self,
        system: str,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.6,
        max_tokens: int | None = None,
    ) -> str:
        out = await self.inner.complete(
            system, messages, temperature=temperature, max_tokens=max_tokens
        )
        input_text = system + "".join(m.content for m in messages)
        self.meter.record(input_text, out)
        return out


def build_role_llm(info, settings: Settings | None = None) -> LLMProvider:
    """Build the executing LLM for a resolved catalog model.

    Honors the existing seam: with LLM_PROVIDER=stub|gemini the run executes as
    before (the chosen catalog model still governs labeling + pricing). With
    LLM_PROVIDER=catalog the chosen provider/model runs for real when its key is
    present (falling back to the offline stub otherwise)."""
    settings = settings or get_settings()
    if settings.llm_provider.lower() == "catalog":
        from providers import catalog

        if catalog.provider_available(info.provider, settings):
            from providers.llm import build_catalog_llm

            return build_catalog_llm(info, settings)
        from providers.llm import StubLLM

        return StubLLM(settings)
    return get_llm(settings)


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
    "MeteredLLM",
    "build_role_llm",
    "get_llm",
    "get_stt",
    "get_tts",
]
