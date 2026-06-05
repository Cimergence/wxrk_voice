# wxrk_voice — Voice Capture Agent

A standalone, dockerized service that runs a **real-time voice interview** to
deep-dive ONE work experience and returns **structured CV data** (skills,
numbers, achievements, STAR stories). `wxrk_backend` talks to it only over
HTTP/WebSocket, so the voice tech can be swapped without touching backend code.

Built to the specs in [`operation_files/`](operation_files/) — `PRD.md`,
`API_CONTRACT.md`, `PROMPT.md`.

```
┌─────────────┐   POST /sessions          ┌──────────────────────────────┐
│ wxrk_backend│ ────────────────────────▶ │  wxrk_voice (this service)   │
│ (owns the   │   experience_context       │  app/   FastAPI surface       │
│  DB + review)│ ◀──────────────────────── │  agent/ LiveKit voice worker  │
└─────────────┘   session_id + join_token  │  providers/ swappable seam    │
       browser mic ──▶ LiveKit room ──────▶│  extraction/ transcript→JSON  │
                                            │  simulate/ LLM-vs-LLM testing │
                                            └──────────────────────────────┘
```

## Quick start

```bash
# 1. run it (boots on offline stub providers — no keys needed)
docker compose -f wxrk_voice/docker-compose.yml up --build

# 2. health check
curl localhost:8080/health
# {"status":"ok","providers":{"llm":"stub","stt":"stub","tts":"stub"}}

# 3. open the self-contained test console
open http://localhost:8080/test
```

The `/test` page has a **Start (mic)** button (live LiveKit interview) and a
**Simulate (no mic)** button that runs a full LLM-vs-LLM interview and renders it
in the chat — no keys, no audio, instant.

### Run locally (no Docker)

```bash
cd wxrk_voice
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080
pytest                       # 22 tests, all offline
```

## The provider seam — swap any layer with one env var

Every provider sits behind an interface (`providers/base.py`) and is chosen
**purely by an env var**. No code changes anywhere.

| Layer | Env var | Default (offline) | Hosted / production | Local swap target |
|-------|---------|-------------------|---------------------|-------------------|
| LLM   | `LLM_PROVIDER` | `stub` | `gemini` (2.5 Flash Lite) | Ollama (`OLLAMA_*`) |
| STT   | `STT_PROVIDER` | `stub` | `deepgram` (Nova-3) | faster-whisper |
| TTS   | `TTS_PROVIDER` | `stub` | `deepgram` (Aura) | Piper |

```bash
# go live: edit .env
LLM_PROVIDER=gemini
STT_PROVIDER=deepgram
TTS_PROVIDER=deepgram
GEMINI_API_KEY=...
DEEPGRAM_API_KEY=...
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

The two LLM implementations (`gemini` hosted + `stub` offline) prove the seam:
changing `LLM_PROVIDER` flips the model and the service still boots and serves
`/sessions` and `/simulate` with zero code edits. See `.env.example` for every
variable.

## API (see `operation_files/API_CONTRACT.md`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/health` | liveness + active providers |
| `POST` | `/sessions` | start a scoped interview → `session_id`, `join_token`, `ws_url` |
| `GET`  | `/sessions/{id}/transcript` | ordered `{speaker,text,ts}` turns |
| `WS`   | `/sessions/{id}/stream` | live turn push for the chat UI |
| `POST` | `/sessions/{id}/finalize` | end session → validated extraction JSON |
| `POST` | `/simulate` | LLM-vs-LLM text interview + extraction (no audio) |
| `GET`  | `/test` | self-contained chat test page |

Auth: set `REQUIRE_AUTH=true` and every call needs `Authorization: Bearer
$SERVICE_API_KEY`.

### `POST /simulate` — cheap end-to-end testing

One LLM plays the candidate against Mira in text mode, then extraction runs.
`difficulty` swaps the persona:

- `easy` — forthcoming candidate; smoke-tests the happy path.
- `hard` (default) — guarded candidate; reveals specifics only when probed, so it
  tests whether Mira actually digs.

```bash
curl -s localhost:8080/simulate -H 'Content-Type: application/json' \
  -d '{"experience_context":"Senior Backend Engineer at Acme. Detected tech: Python, Postgres, Kafka, AWS","difficulty":"hard"}' | jq
# -> { "transcript": [...], "extraction": {...}, "ground_truth": {...} }
```

## Live audio pipeline

The mic path uses **LiveKit Agents** (STT → LLM → TTS with VAD, turn detection,
barge-in), driven by the live interview prompt. The worker runs as a separate
process and reports each turn back to the API:

```bash
docker compose -f wxrk_voice/docker-compose.yml --profile live up --build
# or locally:  python -m agent.interview_agent dev   (needs requirements-voice.txt)
```

## Wiring into the root WXRK stack (one manual step)

This service is self-contained. To run it alongside the rest of WXRK, add **one
block** to the repo-root `docker-compose.yml`:

```yaml
  wxrk_voice:
    build: ./wxrk_voice
    env_file: ./wxrk_voice/.env
    ports: ["8080:8080"]
```

The voice service never reads the backend DB — `wxrk_backend` assembles
`experience_context` and passes it in the `POST /sessions` body.

## Layout

```
wxrk_voice/
├── app/           FastAPI: health, sessions, transcript, WS, finalize, simulate, /test
├── agent/         LiveKit voice worker + prompt loader (reads operation_files/PROMPT.md)
├── providers/     LLMProvider / STTProvider / TTSProvider — interface + 2 impls each
├── extraction/    transcript → validated CV-data JSON (extraction prompt + schema)
├── simulate/      text-mode interviewer ↔ candidate harness + persona generator
├── static/        test.html — self-contained chat console
├── tests/         pytest suite (offline, no keys)
└── operation_files/  the source specs (PRD, API contract, prompts, goal)
```
