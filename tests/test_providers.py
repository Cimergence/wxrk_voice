"""The provider seam: switching an implementation is an env change, nothing else."""
import asyncio

import pytest

from app.config import reset_settings_cache
from providers import get_llm, get_stt, get_tts
from providers.base import ChatMessage, LLMProvider, STTProvider, TTSProvider


def _select(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    reset_settings_cache()


def test_llm_seam_two_impls_via_env(monkeypatch):
    # Same call site, two implementations, chosen purely by env var.
    _select(monkeypatch, LLM_PROVIDER="stub")
    stub = get_llm()
    assert isinstance(stub, LLMProvider) and stub.name == "stub"

    _select(monkeypatch, LLM_PROVIDER="gemini")
    gemini = get_llm()
    assert isinstance(gemini, LLMProvider) and gemini.name == "gemini"

    assert type(stub) is not type(gemini)


def test_stt_seam(monkeypatch):
    _select(monkeypatch, STT_PROVIDER="stub")
    assert isinstance(get_stt(), STTProvider) and get_stt().name == "stub"
    _select(monkeypatch, STT_PROVIDER="deepgram")
    assert isinstance(get_stt(), STTProvider) and get_stt().name == "deepgram"


def test_tts_seam(monkeypatch):
    _select(monkeypatch, TTS_PROVIDER="stub")
    assert isinstance(get_tts(), TTSProvider) and get_tts().name == "stub"
    _select(monkeypatch, TTS_PROVIDER="deepgram")
    assert isinstance(get_tts(), TTSProvider) and get_tts().name == "deepgram"


def test_unknown_provider_raises(monkeypatch):
    _select(monkeypatch, LLM_PROVIDER="bogus")
    with pytest.raises(ValueError):
        get_llm()


async def test_stub_llm_callable_no_keys(monkeypatch):
    _select(monkeypatch, LLM_PROVIDER="stub")
    llm = get_llm()
    out = await llm.complete("You are Mira, an interviewer.", [])
    assert isinstance(out, str) and out.strip()


async def test_stub_stt_tts_callable(monkeypatch):
    _select(monkeypatch, STT_PROVIDER="stub", TTS_PROVIDER="stub")
    assert await get_stt().transcribe(b"\x00\x00") == "[stub transcript]"
    audio = await get_tts().synthesize("hello")
    assert audio[:4] == b"RIFF" and len(audio) > 44
