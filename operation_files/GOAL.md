# Claude Code — Goal (WXRK monorepo)

> Spec files live in `wxrk_voice/operation_files/`. The service is built into
> `wxrk_voice/` (next to `operation_files/`). Nothing outside `wxrk_voice/` is touched —
> `wxrk_backend`, `wxrk_frontend`, and the root `docker-compose.yml` stay clean.

## 1. Branch setup
```bash
git checkout -b feat/wxrk-voice-capture
```

## 2. Goal condition (paste into Claude Code)
```
/goal
Build a standalone, dockerized voice interview service inside the existing wxrk_voice/ folder of the WXRK monorepo, following wxrk_voice/operation_files/PRD.md, wxrk_voice/operation_files/API_CONTRACT.md, and the two prompts in wxrk_voice/operation_files/PROMPT.md. All new code goes under wxrk_voice/ alongside the existing operation_files/ folder. No file outside wxrk_voice/ may be created or modified — wxrk_backend/, wxrk_frontend/, wxrk_landing_v2/, and the root docker-compose.yml must stay untouched.

First, scaffold the service under wxrk_voice/ (e.g. wxrk_voice/app/, wxrk_voice/Dockerfile, wxrk_voice/docker-compose.yml for standalone runs, wxrk_voice/.env.example listing every provider env var: LLM_PROVIDER, STT_PROVIDER, TTS_PROVIDER plus keys and the documented swap targets, and wxrk_voice/README.md). FastAPI app exposes GET /health returning 200. Verify `docker compose -f wxrk_voice/docker-compose.yml up` boots and `curl localhost:8080/health` returns 200. Then commit "checkpoint: wxrk_voice service scaffold boots, health ok".

Then build the provider seam: interfaces LLMProvider, STTProvider, TTSProvider in wxrk_voice/providers/, each with TWO implementations (hosted default + a local/stub impl), selected purely by env var. Add a unit test that loads each provider via env and asserts the seam works with no code change. `pytest wxrk_voice/` exits 0. Then commit "checkpoint: swappable provider seam, two LLMs, tests green".

Then build the live voice pipeline in wxrk_voice/agent/ using LiveKit Agents (STT -> LLM -> TTS, VAD, turn detection, barge-in), driven by the live interview prompt from operation_files/PROMPT.md with {{EXPERIENCE_CONTEXT}} injected from the POST /sessions body (wxrk_backend supplies it; the service never reads the backend DB). Implement POST /sessions (accepts experience context, returns session_id + join_token + ws_url), capture every turn as {speaker,text,ts}, expose GET /sessions/{id}/transcript and WS /sessions/{id}/stream. Then commit "checkpoint: voice pipeline + transcript capture wired".

Then build extraction: POST /sessions/{id}/finalize runs the extraction prompt over the transcript and returns JSON that validates against the schema in operation_files/PROMPT.md (parse it and assert required keys exist). Add a test feeding a sample transcript fixture asserting valid schema JSON out. `pytest wxrk_voice/` exits 0. Then commit "checkpoint: structured extraction returns valid schema".

Then build the text-mode simulation harness in wxrk_voice/simulate/ and POST /simulate, using the candidate simulator and persona generator prompts from operation_files/PROMPT.md: one LLM impersonates the candidate and answers the interviewer in a text loop (no audio), then extraction runs over the resulting transcript. It accepts a difficulty flag (easy = forthcoming candidate, hard = guarded candidate that reveals specifics only when probed; default hard), injecting the matching BEHAVIOR MODE block from PROMPT.md. Given an experience_context it generates a persona with ground_truth, runs up to max_turns, and returns transcript + extraction + ground_truth. Add a test asserting BOTH difficulty modes yield a non-empty transcript and valid extraction JSON, and that the easy run recovers at least as many ground_truth metrics as the hard run. `pytest wxrk_voice/` exits 0. Then commit "checkpoint: LLM-vs-LLM simulation harness works". 

Then build wxrk_voice/static/test.html served at GET /test: a self-contained chat page that creates a session, joins the LiveKit room with the browser mic, and renders the live transcript as a two-column chat (agent vs candidate) updating from the WS stream, with one obvious Start (mic) button, a Simulate (no mic) button that calls /simulate and renders the simulated chat, and a visible recording indicator. No wxrk_frontend changes. Then commit "checkpoint: self-contained /test chat page works".

Final: from a clean `docker compose -f wxrk_voice/docker-compose.yml up`, /health is 200, wxrk_voice/README.md documents how to run, how to swap each provider via env, and the one service block to add to the root docker-compose.yml later; POST /simulate returns a transcript and valid extraction JSON with no audio in both easy and hard difficulty modes; changing LLM_PROVIDER to the second implementation still boots and serves /sessions and /simulate; `pytest wxrk_voice/` exits 0; and `git diff --name-only main` shows only files under wxrk_voice/. Or stop after 60 turns.
```

## 3. What this enforces
- **Fits WXRK:** builds into your existing `wxrk_voice/` folder, reads the specs
  from `wxrk_voice/operation_files/`, and the final `git diff` check proves
  `wxrk_backend`, `wxrk_frontend`, and root files were never touched.
- **Standalone compose:** the service gets its own `wxrk_voice/docker-compose.yml`
  so it runs and tests in isolation. Wiring it into your **root** `docker-compose.yml`
  is left as a documented one-line manual step (the goal can't touch root, by design).
- **Swap requirement is tested:** flipping `LLM_PROVIDER` must still boot — the
  whole reason for a separate service.
- **Checkpoints** at each seam give you rollback points across the 5 phases.
- **60-turn cap** bounds the unattended run; Ctrl+C if it stalls.

## 4. The one manual step after the build
Add this to your **root** `docker-compose.yml` to run the voice service with the rest of WXRK:
```yaml
  wxrk_voice:
    build: ./wxrk_voice
    env_file: ./wxrk_voice/.env
    ports: ["8080:8080"]
```
