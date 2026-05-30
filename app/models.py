"""Pydantic request/response models mirroring operation_files/API_CONTRACT.md."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Turn(BaseModel):
    speaker: Literal["agent", "user"]
    text: str
    ts: float


class CreateSessionRequest(BaseModel):
    experience_id: str = "exp_unknown"
    candidate_name: Optional[str] = None
    experience_context: str = Field(..., min_length=1)


class CreateSessionResponse(BaseModel):
    session_id: str
    room: str
    join_token: str
    ws_url: str


class TranscriptResponse(BaseModel):
    session_id: str
    status: Literal["active", "ended"]
    turns: list[Turn]


class FinalizeResponse(BaseModel):
    session_id: str
    experience_id: str
    data: dict[str, Any]


class SimulateRequest(BaseModel):
    experience_context: Optional[str] = None
    persona: Optional[dict[str, Any]] = None
    difficulty: Literal["easy", "hard"] = "hard"
    max_turns: int = 16


class SimulateResponse(BaseModel):
    transcript: list[Turn]
    extraction: dict[str, Any]
    ground_truth: Optional[dict[str, Any]] = None
