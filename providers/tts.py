"""TTS implementations: DeepgramTTS (hosted Aura) + StubTTS (offline)."""
from __future__ import annotations

import struct

import httpx

from app.config import Settings
from providers.base import TTSProvider


class DeepgramTTS(TTSProvider):
    name = "deepgram"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.deepgram_tts_model

    async def synthesize(self, text: str) -> bytes:
        if not self.settings.deepgram_api_key:
            raise RuntimeError("TTS_PROVIDER=deepgram but DEEPGRAM_API_KEY is unset.")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/speak",
                params={"model": self.model},
                headers={
                    "Authorization": f"Token {self.settings.deepgram_api_key}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
            )
            resp.raise_for_status()
            return resp.content


class StubTTS(TTSProvider):
    """Offline stand-in: returns a tiny silent WAV so callers get valid bytes."""

    name = "stub"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def synthesize(self, text: str) -> bytes:
        sample_rate = 16000
        n = 1600  # 0.1s of silence
        data = b"\x00\x00" * n
        header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
        header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate,
                                        sample_rate * 2, 2, 16)
        header += b"data" + struct.pack("<I", len(data))
        return header + data
