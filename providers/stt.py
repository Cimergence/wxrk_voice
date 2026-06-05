"""STT implementations: DeepgramSTT (hosted Nova-3) + StubSTT (offline)."""
from __future__ import annotations

import httpx

from app.config import Settings
from providers.base import STTProvider


class DeepgramSTT(STTProvider):
    name = "deepgram"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.deepgram_stt_model

    async def transcribe(self, audio: bytes, *, sample_rate: int = 16000) -> str:
        if not self.settings.deepgram_api_key:
            raise RuntimeError("STT_PROVIDER=deepgram but DEEPGRAM_API_KEY is unset.")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                params={"model": self.model, "smart_format": "true"},
                headers={
                    "Authorization": f"Token {self.settings.deepgram_api_key}",
                    "Content-Type": "audio/wav",
                },
                content=audio,
            )
            resp.raise_for_status()
            data = resp.json()
        return data["results"]["channels"][0]["alternatives"][0]["transcript"]


class StubSTT(STTProvider):
    """Offline stand-in. The live audio path uses LiveKit plugins directly; this
    exists to prove the seam and to support non-audio tests."""

    name = "stub"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def transcribe(self, audio: bytes, *, sample_rate: int = 16000) -> str:
        return "[stub transcript]"
