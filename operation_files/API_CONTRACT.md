# API Contract — Voice Capture Agent

Base URL: `http://wxrk_voice:8080` (inside Docker network).
Auth: shared bearer token via `SERVICE_API_KEY` header on every call.

## POST /sessions
Start a scoped interview for one experience. Creates the LiveKit room, mints the
browser join token, and ensures the agent is dispatched to that room (automatic
dispatch with no agent_name, or an explicit dispatch call here).
```json
// request
{
  "experience_id": "exp_123",
  "candidate_name": "Sara",
  "experience_context": "Senior Backend Engineer at Acme, 2021–2023. Built the
    payments service. Detected tech: Python, Postgres, Kafka, AWS.",
  "convo": {"provider":"xai","model":"grok-4.3"},      // optional; defaults to CONVO_PROVIDER/env resolution
  "extract": {"provider":"openai","model":"gpt-5.4-mini"}  // optional; defaults to EXTRACT_PROVIDER/env resolution
}
// response
{
  "session_id": "sess_abc",
  "room": "voice-sess_abc",
  "join_token": "eyJ...",          // LiveKit token for the frontend mic client
  "ws_url": "wss://your-project.livekit.cloud"
}
```

## GET /sessions/{id}/transcript
Live or final transcript for the chat UI. Poll, or subscribe to the WS below.
```json
{
  "session_id": "sess_abc",
  "status": "active",              // active | ended
  "turns": [
    {"speaker": "agent", "text": "Walk me through what you did day to day.", "ts": 1730000000},
    {"speaker": "user",  "text": "I owned the payments pipeline...",        "ts": 1730000007}
  ]
}
```

## WS /sessions/{id}/stream  (optional, preferred for the test page)
Server pushes `{"type":"turn","speaker":...,"text":...,"ts":...}` as each turn
is finalized. Lets the chat panel update without polling.

## POST /sessions/{id}/finalize
Ends the session and returns structured CV data (extraction schema).
```json
{
  "session_id": "sess_abc",
  "experience_id": "exp_123",
  "data": {
    "role_summary": "...",
    "scope": "...",
    "skills": ["..."],
    "metrics": [{"claim":"...","value":"...","before":null}],
    "achievements": ["..."],
    "star_stories": [{"situation":"","task":"","action":"","result":""}],
    "quotes": ["..."],
    "gaps": ["..."]
  },
  "cost": {
    "total_usd": 0.0123,
    "convo": {"model":"xai-grok-4.3","in_tokens":4200,"out_tokens":1100,"usd":0.0081},
    "extract": {"model":"openai-gpt-5.4-mini","in_tokens":3000,"out_tokens":600,"usd":0.0042}
  }
}
```

## GET /sessions/{id}/cost
Running USD cost for a session (live or final), broken down by role and model.
```json
{ "session_id":"sess_abc", "total_usd":0.0123,
  "convo":{"model":"xai-grok-4.3","in_tokens":4200,"out_tokens":1100,"usd":0.0081},
  "extract":{"model":"openai-gpt-5.4-mini","in_tokens":3000,"out_tokens":600,"usd":0.0042} }
```

## GET /health
`200 {"status":"ok","providers":{"convo":"xai/grok-4.3","extract":"openai/gpt-5.4-nano","stt":"deepgram","tts":"deepgram"}}`

## GET /test
Self-contained chat test page. Creates a throwaway session, joins the room with
the browser mic, and renders the live transcript. No backend involvement.

## Where experience_context comes from
`wxrk_backend` owns the technical review. It assembles `experience_context` for the
chosen experience and passes it in the `POST /sessions` body. The voice service
never reads the backend DB or schema — it only receives the context. (To auto-test
with a *real* stored user later, add a small read endpoint in `wxrk_backend`; that's
a separate backend task and out of scope for this service.)

## POST /simulate  (testing only — no mic, no audio)
Runs an LLM-impersonated candidate against the interviewer in text mode, then
extracts. Cheap and fast; ideal for CI and tuning the prompt. `difficulty` swaps
the candidate persona: `easy` = forthcoming (smoke test the happy path),
`hard` = guarded, reveals specifics only when probed (tests whether Mira digs).
```json
// request — give EITHER a ready persona OR an experience_context to auto-build one
{
  "experience_context": "Senior Backend Engineer at Acme...",  // optional
  "persona": { "...persona JSON..." },                          // optional
  "difficulty": "hard",                                          // "easy" | "hard" (default "hard")
  "convo": {"provider":"xai","model":"grok-4.3"},                // optional override
  "extract": {"provider":"openai","model":"gpt-5.4-mini"},       // optional override
  "max_turns": 16
}
// response
{
  "transcript": [
    {"speaker":"agent","text":"...","ts":0},
    {"speaker":"user","text":"...","ts":1}
  ],
  "extraction": { "...extraction schema JSON..." },
  "ground_truth": { "...if a persona was generated, for scoring..." },
  "cost": { "total_usd": 0.004, "convo": {"...":"..."}, "extract": {"...":"..."} }
}
```
