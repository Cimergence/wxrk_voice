# PRD — Voice Capture Agent (standalone service)

## Purpose
A self-contained, dockerized service that runs a **real-time voice interview**
to deep-dive ONE work experience and returns **structured CV data**
(skills, numbers, achievements, STAR stories). `wxrk_backend` talks to it
only over HTTP/WebSocket, so the voice tech can be swapped without touching
backend code.

## Hard rules (non-negotiable)
1. **Lives in its own folder/repo** (`wxrk_voice/`). No imports from
   wxrk_backend. No wxrk_backend or wxrk_frontend file is modified by this work.
2. **All providers are config-driven** behind interfaces: `LLMProvider`,
   `STTProvider`, `TTSProvider`. Switching provider = changing an env var, nothing
   else. Ship at least two LLM implementations (hosted default + local stub) to
   prove the seam works.
3. **One experience per session.** `experience_context` is passed in by `wxrk_backend`
   at session creation (the service never reads the backend DB). Not hardcoded.
4. **Every turn is captured as text** (speaker, text, timestamp) and exposed so a
   chat UI can render the conversation live.
5. **Serves its own `/test` page** — a minimal chat interface that connects mic,
   shows the live transcript, and needs zero backend changes to run.

## Components
- `app/` — FastAPI service: session lifecycle, token mint, transcript stream,
  extraction, health.
- `agent/` — LiveKit voice pipeline (STT → LLM → TTS, VAD, turn detection,
  barge-in) using the live interview prompt from `PROMPT.md`.
- `providers/` — `llm.py`, `stt.py`, `tts.py`, each an interface + 2 impls.
- `extraction/` — post-call transcript → JSON using the extraction prompt.
- `simulate/` — text-mode harness: interviewer-LLM ↔ candidate-LLM loop (no
  audio) + persona generator, for fast/cheap end-to-end testing (`POST /simulate`).
- `static/test.html` — self-contained chat test page served at `/test`.
- `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`.

## Default config
- Transport: LiveKit Cloud (WebRTC, barge-in).
- STT: Deepgram Nova-3. LLM: Gemini 2.5 Flash Lite. TTS: Deepgram Aura.
- Swap targets documented in `.env.example`: local `faster-whisper`,
  Ollama small model, Piper TTS.

## Success = these are all true
- `docker compose up` starts the service; `GET /health` returns 200.
- Opening `/test`, allowing mic, and speaking produces a back-and-forth voice
  conversation with the agent, and the transcript renders live in the chat panel.
- `POST /sessions` accepts an experience context and starts a scoped interview.
- `GET /sessions/{id}/transcript` returns ordered turns with speaker + text.
- `POST /sessions/{id}/finalize` returns valid JSON matching the extraction schema.
- `POST /simulate` runs an LLM-impersonated candidate against the interviewer in
  text mode and returns a full transcript plus valid extraction JSON, no audio used.
- Changing `LLM_PROVIDER` in env switches the model with no code edit and the
  service still boots and runs the conversation.
- `git diff --name-only` shows only files under `wxrk_voice/`.

## Out of scope (separate, later task)
- The `/voice-capture-test` page in `wxrk_frontend`. It will just embed the
  same endpoints; the service's own `/test` page proves the flow first.

## API contract
See `API_CONTRACT.md`.

## Prompts
See `PROMPT.md` (live interview prompt + extraction prompt).
