"""FastAPI surface for the Voice Capture Agent.

Implements operation_files/API_CONTRACT.md:
  GET  /health
  POST /sessions
  GET  /sessions/{id}/transcript
  WS   /sessions/{id}/stream
  POST /sessions/{id}/finalize
  POST /simulate
  GET  /test
  POST /internal/sessions/{id}/turn   (live worker callback — not part of the
                                        public contract)
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import get_settings
from app.livekit_token import mint_join_token
from app.models import (
    CreateSessionRequest,
    CreateSessionResponse,
    FinalizeResponse,
    SimulateRequest,
    SimulateResponse,
    TranscriptResponse,
)
from app.sessions import store
from extraction.extract import run_extraction
from providers import get_llm
from simulate.harness import run_simulation

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="WXRK Voice Capture Agent", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_service_auth(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.require_auth:
        return
    expected = f"Bearer {settings.service_api_key}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing service token")


# --------------------------------------------------------------------------- #
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "providers": get_settings().provider_summary}


@app.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    req: CreateSessionRequest, _: None = Depends(require_service_auth)
) -> CreateSessionResponse:
    settings = get_settings()
    session = store.create(
        experience_id=req.experience_id,
        experience_context=req.experience_context,
        candidate_name=req.candidate_name,
    )
    join_token, ws_url = mint_join_token(
        settings, session.room, identity=req.candidate_name or "candidate"
    )
    return CreateSessionResponse(
        session_id=session.session_id,
        room=session.room,
        join_token=join_token,
        ws_url=ws_url,
    )


@app.get("/sessions/{session_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    session_id: str, _: None = Depends(require_service_auth)
) -> TranscriptResponse:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return TranscriptResponse(
        session_id=session.session_id, status=session.status, turns=session.turns
    )


@app.post("/sessions/{session_id}/finalize", response_model=FinalizeResponse)
async def finalize(
    session_id: str, _: None = Depends(require_service_auth)
) -> FinalizeResponse:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        data = await run_extraction(session.turns, get_llm())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"extraction failed: {exc}")
    store.end(session_id)
    return FinalizeResponse(
        session_id=session.session_id, experience_id=session.experience_id, data=data
    )


@app.post("/simulate", response_model=SimulateResponse)
async def simulate(
    req: SimulateRequest, _: None = Depends(require_service_auth)
) -> SimulateResponse:
    try:
        return await run_simulation(req, get_llm())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # provider/network failure (e.g. missing API key)
        raise HTTPException(status_code=502, detail=f"provider error: {exc}")


@app.post("/internal/sessions/{session_id}/turn")
async def report_turn(
    session_id: str, body: dict, _: None = Depends(require_service_auth)
) -> dict:
    """Called by the live LiveKit worker as each turn finalizes."""
    turn = await store.add_turn(
        session_id, body.get("speaker", "agent"), body.get("text", ""), body.get("ts")
    )
    if turn is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True}


@app.websocket("/sessions/{session_id}/stream")
async def stream(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    session = store.get(session_id)
    if session is None:
        await websocket.send_json({"type": "error", "detail": "session not found"})
        await websocket.close()
        return
    # Replay turns so far, then live-follow.
    for t in session.turns:
        await websocket.send_json({"type": "turn", **t.model_dump()})
    queue = store.subscribe(session_id)
    try:
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15)
                await websocket.send_json(payload)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        store.unsubscribe(session_id, queue)


@app.get("/test")
async def test_page() -> FileResponse:
    path = STATIC_DIR / "test.html"
    if not path.exists():
        return JSONResponse(status_code=404, content={"detail": "test page missing"})
    return FileResponse(path)


@app.get("/")
async def root() -> dict:
    return {"service": "wxrk_voice", "docs": "/docs", "test_page": "/test"}
