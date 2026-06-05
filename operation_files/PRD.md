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
5. **Agent must actually join the test room.** Either run the worker with automatic
   dispatch (no `agent_name` set) so it auto-joins any new room, OR have `POST /sessions`
   explicitly dispatch the agent to the room it creates. Never leave a room that a
   participant joins with no agent assigned.
6. **Serves its own `/test` page** — a minimal chat interface that connects mic,
   shows the live transcript, and needs zero backend changes to run.

## Components
- `app/` — FastAPI service: session lifecycle, token mint, transcript stream,
  extraction, health.
- `agent/` — LiveKit voice pipeline (STT → LLM → TTS, VAD, turn detection,
  barge-in) using the live interview prompt from `PROMPT.md`.
- `providers/` — `llm.py`, `stt.py`, `tts.py`, each an interface + 2 impls.
- `extraction/` — post-call transcript → JSON using the extraction prompt.
- `observability/` — per-call cost tracking: read MODELS.md prices, multiply by
  actual input/output tokens from each provider response, store per-turn and
  per-session USD totals, expose them via API and show them on the test page.
- `simulate/` — text-mode harness: interviewer-LLM ↔ candidate-LLM loop (no
  audio) + persona generator, for fast/cheap end-to-end testing (`POST /simulate`).
- `static/test.html` — self-contained chat test page served at `/test`.
- `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`.

## Default config
- Transport: LiveKit Cloud (WebRTC, barge-in).
- STT: Deepgram Nova-3. TTS: Deepgram Aura.
- **Two independent LLM settings**, both choosable from the SAME three providers (no Gemini, no Groq): **OpenAI, xAI, Anthropic**.
  The model list + prices live in `operation_files/MODELS.md` (single source of truth).
  - **Conversation role** (latency-critical): `CONVO_PROVIDER` + model resolution.
  - **Extraction role** (JSON quality): `EXTRACT_PROVIDER` + model resolution.
- Model resolution per role: `*_MODEL` (role) → `<PROVIDER>_MODEL` → `<PROVIDER>_MODEL_DEFAULT`
  (see MODELS.md). Switching is env-only. Each provider reads its own key
  (OPENAI_API_KEY, XAI_API_KEY, ANTHROPIC_API_KEY); a provider is selectable only
  if its key is present.
- Optional later swap targets: local `faster-whisper` (STT), Piper (TTS).

## Success = these are all true
- `docker compose up` starts the service; `GET /health` returns 200.
- Opening `/test`, allowing mic, and speaking produces a back-and-forth voice
  conversation with the agent, and the transcript renders live in the chat panel.
- `POST /sessions` accepts an experience context and starts a scoped interview.
- `GET /sessions/{id}/transcript` returns ordered turns with speaker + text.
- `POST /sessions/{id}/finalize` returns valid JSON matching the extraction schema.
- Every session and every /simulate run reports a USD cost breakdown (per role:
  conversation vs extraction, plus tokens used and the model that ran). Costs use
  the prices in MODELS.md and the real token counts from provider responses.
- `POST /simulate` runs an LLM-impersonated candidate against the interviewer in
  text mode and returns a full transcript plus valid extraction JSON, no audio used.
- Setting `CONVO_PROVIDER`/`EXTRACT_PROVIDER` (and the model vars) to any
  key-present provider switches each role with no code edit; the service still boots.
- The `/test` page lets you pick the conversation model and the extraction model
  before running, so model combos can be A/B tested without a rebuild.
- `git diff --name-only` shows only files under `wxrk_voice/`.

## Out of scope (separate, later task)
- The `/voice-capture-test` page in `wxrk_frontend`. It will just embed the
  same endpoints; the service's own `/test` page proves the flow first.

## API contract
See `API_CONTRACT.md`.

## Prompts
See `PROMPT.md` (live interview prompt + extraction prompt).
