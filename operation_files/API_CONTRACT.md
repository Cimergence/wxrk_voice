# API Contract — Voice Capture Agent

Base URL: `http://voice-capture-agent:8080` (inside Docker network).
Auth: shared bearer token via `SERVICE_API_KEY` header on every call.

## POST /sessions
Start a scoped interview for one experience.
```json
// request
{
  "experience_id": "exp_123",
  "candidate_name": "Sara",
  "experience_context": "Senior Backend Engineer at Acme, 2021–2023. Built the
    payments service. Detected tech: Python, Postgres, Kafka, AWS."
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
  }
}
```

## GET /health
`200 {"status":"ok","providers":{"llm":"gemini","stt":"deepgram","tts":"deepgram"}}`

## GET /test
Self-contained chat test page. Creates a throwaway session, joins the room with
the browser mic, and renders the live transcript. No backend involvement.
