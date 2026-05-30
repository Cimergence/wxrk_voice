"""LiveKit voice worker: STT → LLM → TTS with VAD, turn detection and barge-in.

Run as a separate process (its own container/command), NOT imported by the API
or the test suite. It joins the room created by POST /sessions, runs Mira from
the live interview prompt with the session's {{EXPERIENCE_CONTEXT}}, and reports
each finalized turn back to the API via POST /internal/sessions/{id}/turn so the
chat UI and GET /sessions/{id}/transcript stay live.

Providers are env-selected to match the rest of the service:
  STT_PROVIDER=deepgram  LLM_PROVIDER=gemini  TTS_PROVIDER=deepgram
(the local swap targets — faster-whisper / Ollama / Piper — plug in the same way).

Start with:
    python -m agent.interview_agent dev      # or `start` in production
Requires the deps in requirements-voice.txt and LiveKit + provider creds.
"""
from __future__ import annotations

import json

import httpx
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import deepgram, google, silero

from agent.prompts import live_interview_prompt
from app.config import get_settings


def _build_llm(settings):
    # The seam: swap by env. Gemini hosted default; Ollama is the local target.
    if settings.llm_provider == "gemini":
        return google.LLM(model=settings.gemini_model, api_key=settings.gemini_api_key)
    # Ollama exposes an OpenAI-compatible API; the openai plugin points at it.
    from livekit.plugins import openai

    return openai.LLM(
        model=settings.ollama_model,
        base_url=f"{settings.ollama_base_url}/v1",
        api_key="ollama",
    )


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Room metadata carries the session_id + experience_context that /sessions set.
    meta = {}
    try:
        meta = json.loads(ctx.room.metadata or "{}")
    except json.JSONDecodeError:
        pass
    session_id = meta.get("session_id", ctx.room.name)
    experience_context = meta.get("experience_context", "this work experience")

    from livekit.agents import llm as lk_llm

    initial_ctx = lk_llm.ChatContext().append(
        role="system", text=live_interview_prompt(experience_context)
    )

    agent = VoicePipelineAgent(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model=settings.deepgram_stt_model, api_key=settings.deepgram_api_key),
        llm=_build_llm(settings),
        tts=deepgram.TTS(model=settings.deepgram_tts_model, api_key=settings.deepgram_api_key),
        chat_ctx=initial_ctx,
        allow_interruptions=True,  # barge-in
    )

    api_base = f"http://localhost:{settings.port}"
    headers = {"Authorization": f"Bearer {settings.service_api_key}"}

    async def _report(speaker: str, text: str) -> None:
        if not text.strip():
            return
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                await client.post(
                    f"{api_base}/internal/sessions/{session_id}/turn",
                    headers=headers,
                    json={"speaker": speaker, "text": text},
                )
            except Exception:
                pass  # transcript reporting is best-effort

    @agent.on("user_speech_committed")
    def _on_user(msg) -> None:  # noqa: ANN001
        import asyncio

        asyncio.create_task(_report("user", msg.content))

    @agent.on("agent_speech_committed")
    def _on_agent(msg) -> None:  # noqa: ANN001
        import asyncio

        asyncio.create_task(_report("agent", msg.content))

    agent.start(ctx.room)
    await agent.say(
        "Hi! I'd love to dig into this experience with you. "
        "Walk me through what you actually did day to day.",
        allow_interruptions=True,
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
