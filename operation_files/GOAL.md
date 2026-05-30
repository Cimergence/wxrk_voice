# Claude Code — Goal

## 1. Branch setup
```bash
git checkout -b feat/voice-capture-agent
```

## 2. Goal condition (paste into Claude Code)
```
/goal
Build a standalone, dockerized voice interview service in a new top-level folder voice-capture-agent/, following voice-capture-agent/PRD.md, voice-capture-agent/API_CONTRACT.md, and the two prompts in voice-capture-agent/PROMPT.md. No file outside voice-capture-agent/ may be created or modified.

First, scaffold the service: FastAPI app with GET /health returning 200, Dockerfile, docker-compose.yml, .env.example listing every provider env var (LLM_PROVIDER, STT_PROVIDER, TTS_PROVIDER + their keys and the documented swap targets), and a README. Verify `docker compose up` boots and `curl localhost:8080/health` returns 200. Then commit "checkpoint: service scaffold boots, health ok".

Then build the provider seam: interfaces LLMProvider, STTProvider, TTSProvider in providers/, each with TWO implementations (hosted default + a local/stub impl), selected purely by env var. Add a unit test that loads each provider via env and asserts the seam works with no code change. `pytest` exits 0. Then commit "checkpoint: swappable provider seam, two LLMs, tests green".

Then build the live voice pipeline in agent/ using LiveKit Agents (STT -> LLM -> TTS, VAD, turn detection, barge-in), driven by the live interview prompt from PROMPT.md with {{EXPERIENCE_CONTEXT}} injected from the session. Implement POST /sessions (accepts experience context, returns session_id + join_token + ws_url), capture every turn as {speaker,text,ts}, expose GET /sessions/{id}/transcript and the WS /sessions/{id}/stream. Then commit "checkpoint: voice pipeline + transcript capture wired".

Then build extraction: POST /sessions/{id}/finalize runs the extraction prompt over the transcript and returns JSON that validates against the schema in PROMPT.md (parse it and assert required keys exist). Add a test that feeds a sample transcript fixture and asserts valid schema JSON out. `pytest` exits 0. Then commit "checkpoint: structured extraction returns valid schema".

Then build static/test.html served at GET /test: a self-contained chat page that creates a session, joins the LiveKit room with the browser mic, and renders the live transcript as a two-column chat (agent vs candidate) updating from the WS stream, with one obvious "Start" button and a visible recording indicator. No backend changes. Then commit "checkpoint: self-contained /test chat page works".

Final: from a clean `docker compose up`, /health is 200, the README documents how to run and how to swap each provider via env, changing LLM_PROVIDER to the second implementation still boots and serves /sessions, `pytest` exits 0, and `git diff --name-only main` shows only files under voice-capture-agent/. Or stop after 60 turns.
```

## 3. What this enforces
- **Intent, not just the check:** each phase names the real deliverable (working
  voice loop, valid extraction JSON, a chat test page that updates live), not only
  "tests pass".
- **The swap requirement is tested**, not assumed — flipping `LLM_PROVIDER` must
  still boot. That is the whole point of the separate service.
- **Scope is locked** to `voice-capture-agent/` via the final `git diff` check, so
  the backend stays untouched.
- **Checkpoints** at each natural seam (scaffold → seam → pipeline → extraction →
  test page) give you commits to roll back to if a later phase breaks an earlier one.
- **60-turn cap** bounds an unattended run; this is a multi-phase build so it needs
  more room than a fix. Ctrl+C if it stalls.

The PRD, API contract, and prompts already exist as files, so the goal stays short
and *points at* them rather than restating everything.
