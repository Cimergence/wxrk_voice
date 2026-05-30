# Claude Code — Goal: admin model selection + backend↔voice wiring (LATER phase)

> Do this AFTER the voice service is tested and working at localhost:8080.
> Goal: the WXRK **admin** lets you choose the **conversation model** and the
> **extraction model** (each: OpenAI, xAI, or Anthropic — no Gemini), and
> `wxrk_backend` talks to the voice service to start sessions and fetch results.
> Touches `wxrk_backend` and `wxrk_frontend` only. The voice service already
> exposes GET /llm/options and accepts convo/extract provider+model per call.

## 1. Branch
```bash
git checkout -b feat/voice-admin-and-backend
```

## 2. Goal condition (paste into Claude Code)
```
/goal
Wire the WXRK app to the working voice service in wxrk_voice/ and let an admin choose the conversation model and the extraction model. Only wxrk_backend/ and wxrk_frontend/ may change. Do not modify wxrk_voice/, wxrk_landing_v2/, or the root docker-compose.yml.

First, DISCOVER and report: how wxrk_backend reads config/secrets and how it makes outbound HTTP calls, and how wxrk_frontend admin pages fetch data and store settings. Write a 10-line summary to wxrk_backend/docs/voice_integration.md. Don't change code yet. Then commit "checkpoint: documented backend HTTP + admin patterns".

Then add a thin voice client in wxrk_backend that calls the voice service over HTTP using the contract in wxrk_voice/operation_files/API_CONTRACT.md: start a session (POST /sessions, passing experience_context plus the admin-selected convo and extract provider+model), read transcript (GET /sessions/{id}/transcript), and finalize (POST /sessions/{id}/finalize). The voice service base URL and shared SERVICE_API_KEY come from backend env (VOICE_SERVICE_URL, VOICE_SERVICE_API_KEY). wxrk_backend assembles experience_context from the technical review it already stores. Add a test that mocks the voice service and asserts the client sends the selected provider+model and parses the finalize JSON. `pytest` exits 0. Then commit "checkpoint: backend voice client + experience_context assembly".

Then expose admin settings. Add backend endpoints to GET the available models (proxy or mirror the voice service GET /llm/options: providers openai|xai|anthropic gated by key presence, plus convo/extract defaults) and to GET/PUT the admin's chosen convo and extract provider+model, persisted where wxrk_backend keeps settings. Validate choices against the allowlist server-side; reject anything else with 400. Never accept an API key from the client. Add a test for persistence and allowlist rejection. `pytest` exits 0. Then commit "checkpoint: admin model settings API".

Then build the admin UI in wxrk_frontend: a settings panel with two dropdowns — Conversation model and Extraction model — populated from the models endpoint, saving via the settings API, showing the active selection. Match existing admin component and data-fetch patterns; no new state library. Then commit "checkpoint: admin model selector UI".

Then make it fast: ensure the backend reuses a pooled HTTP client (keep-alive) for voice calls rather than a new connection per request, and that starting a session does not block on anything that can be done concurrently. Add or update a test asserting the client is reused. `pytest` exits 0. Then commit "checkpoint: pooled voice client".

Final: the admin can select a conversation provider+model and an extraction provider+model from {openai, xai, anthropic}; the selection persists; wxrk_backend starts a voice session passing those models and can fetch the finalized extraction; off-allowlist selections are rejected with 400; no API key is accepted from the client; backend tests pass; and `git diff --name-only main` shows only files under wxrk_backend/ and wxrk_frontend/. Or stop after 50 turns.
```

## 3. Why it's shaped this way
- **Two model choices, not one:** conversation (speed) and extraction (JSON
  quality) are tuned separately — matches how the voice service is built.
- **Discovery-first:** documents your real backend/admin patterns before editing.
- **Allowlist + server-side keys:** admin picks an id; keys stay in env on the
  backend and the voice service. No key ever crosses to the client.
- **Backend owns experience_context:** it assembles it from the technical review;
  the voice service stays ignorant of your DB.
- **"Make it fast" is concrete:** pooled keep-alive HTTP client + no needless
  blocking, with a test — not a vague aspiration.
- **Scope-locked** to `wxrk_backend` + `wxrk_frontend`.

## 4. Backend env to add
```
VOICE_SERVICE_URL=http://wxrk_voice:8080
VOICE_SERVICE_API_KEY=<shared secret, same as the voice service>
```
