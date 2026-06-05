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

from app.config import Settings, get_settings
from app.livekit_token import mint_join_token
from app.models import (
    CreateSessionRequest,
    CreateSessionResponse,
    FinalizeResponse,
    ModelChoice,
    SimulateRequest,
    SimulateResponse,
    TranscriptResponse,
)
from app.sessions import store
from extraction.extract import run_extraction
from providers import MeteredLLM, build_role_llm, catalog, get_llm
from providers.catalog import RoleMeter
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


def _choice_tuple(choice: ModelChoice | None) -> tuple[str, str] | None:
    return (choice.provider, choice.model) if choice else None


def _as_choice(stored: tuple[str, str] | None) -> ModelChoice | None:
    return ModelChoice(provider=stored[0], model=stored[1]) if stored else None


def _resolve_role(role: str, choice: ModelChoice | None, settings: Settings):
    """Resolve a role's catalog model; turn off-catalog choices into a 400."""
    try:
        return catalog.resolve_role(role, _choice_tuple(choice), settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------------------- #
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "providers": get_settings().provider_summary}


@app.get("/llm/options")
async def llm_options(_: None = Depends(require_service_auth)) -> dict:
    """Key-gated provider+model catalog for the test page dropdowns. Only models
    whose provider's API key env var is present are returned, split by role."""
    settings = get_settings()

    def serialize(mi) -> dict:
        return {"id": mi.id, "provider": mi.provider, "model": mi.model,
                "in": mi.in_rate, "out": mi.out_rate}

    convo = [serialize(mi) for mi in catalog.available_for_role("convo", settings)]
    extract = [serialize(mi) for mi in catalog.available_for_role("extract", settings)]
    convo_default = catalog.resolve_default("convo", settings)
    extract_default = catalog.resolve_default("extract", settings)
    return {
        "convo": convo,
        "extract": extract,
        "defaults": {
            "convo": serialize(convo_default) if convo_default else None,
            "extract": serialize(extract_default) if extract_default else None,
        },
    }


@app.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    req: CreateSessionRequest, _: None = Depends(require_service_auth)
) -> CreateSessionResponse:
    settings = get_settings()
    convo = _resolve_role("convo", req.convo, settings)
    extract = _resolve_role("extract", req.extract, settings)
    session = store.create(
        experience_id=req.experience_id,
        experience_context=req.experience_context,
        candidate_name=req.candidate_name,
        convo_choice=(convo.provider, convo.model),
        extract_choice=(extract.provider, extract.model),
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
    settings = get_settings()
    convo_info = _resolve_role("convo", _as_choice(session.convo_choice), settings)
    extract_info = _resolve_role("extract", _as_choice(session.extract_choice), settings)
    extract_meter = RoleMeter("extract", extract_info)
    extract_llm = MeteredLLM(build_role_llm(extract_info, settings), extract_meter)
    try:
        data = await run_extraction(session.turns, extract_llm)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"extraction failed: {exc}")
    # Convo cost: the live worker isn't metered here, so estimate from the
    # finalized transcript text, priced by the session's chosen convo model.
    convo_meter = RoleMeter("convo", convo_info)
    all_text = " ".join(t.text for t in session.turns)
    agent_text = " ".join(t.text for t in session.turns if t.speaker == "agent")
    convo_meter.record(all_text, agent_text)
    store.end(session_id)
    return FinalizeResponse(
        session_id=session.session_id,
        experience_id=session.experience_id,
        data=data,
        cost=catalog.cost_block(convo_meter, extract_meter),
    )


@app.post("/simulate", response_model=SimulateResponse)
async def simulate(
    req: SimulateRequest, _: None = Depends(require_service_auth)
) -> SimulateResponse:
    settings = get_settings()
    convo_info = _resolve_role("convo", req.convo, settings)      # 400 on off-catalog
    extract_info = _resolve_role("extract", req.extract, settings)
    convo_meter = RoleMeter("convo", convo_info)
    extract_meter = RoleMeter("extract", extract_info)
    convo_llm = MeteredLLM(build_role_llm(convo_info, settings), convo_meter)
    extract_llm = MeteredLLM(build_role_llm(extract_info, settings), extract_meter)
    try:
        resp = await run_simulation(req, convo_llm=convo_llm, extract_llm=extract_llm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # provider/network failure (e.g. missing API key)
        raise HTTPException(status_code=502, detail=f"provider error: {exc}")
    resp.cost = catalog.cost_block(convo_meter, extract_meter)  # priced after the run
    return resp


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
