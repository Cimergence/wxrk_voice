"""In-memory session + transcript store with live fan-out for the WS stream.

The live audio worker (agent/) runs as a separate LiveKit process and reports
each finalized turn back via POST /internal/sessions/{id}/turn, which lands here
and is broadcast to any WS subscribers. No database — the service is stateless
across restarts by design (the backend owns persistence).
"""
from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from app.models import Turn


@dataclass
class Session:
    session_id: str
    experience_id: str
    experience_context: str
    candidate_name: Optional[str]
    room: str
    status: Literal["active", "ended"] = "active"
    # resolved (provider, model) for each role, for cost/labeling at finalize
    convo_choice: Optional[tuple[str, str]] = None
    extract_choice: Optional[tuple[str, str]] = None
    turns: list[Turn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    _subscribers: set[asyncio.Queue] = field(default_factory=set)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(
        self,
        experience_id: str,
        experience_context: str,
        candidate_name: Optional[str] = None,
        convo_choice: Optional[tuple[str, str]] = None,
        extract_choice: Optional[tuple[str, str]] = None,
    ) -> Session:
        sid = f"sess_{secrets.token_hex(6)}"
        session = Session(
            session_id=sid,
            experience_id=experience_id,
            experience_context=experience_context,
            candidate_name=candidate_name,
            room=f"voice-{sid}",
            convo_choice=convo_choice,
            extract_choice=extract_choice,
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    async def add_turn(self, session_id: str, speaker: str, text: str,
                       ts: Optional[float] = None) -> Optional[Turn]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        turn = Turn(speaker=speaker, text=text, ts=ts if ts is not None else time.time())
        session.turns.append(turn)
        payload = {"type": "turn", **turn.model_dump()}
        for q in list(session._subscribers):
            q.put_nowait(payload)
        return turn

    def end(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.status = "ended"
            for q in list(session._subscribers):
                q.put_nowait({"type": "end", "session_id": session_id})

    def subscribe(self, session_id: str) -> Optional[asyncio.Queue]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        q: asyncio.Queue = asyncio.Queue()
        session._subscribers.add(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        session = self._sessions.get(session_id)
        if session:
            session._subscribers.discard(q)


store = SessionStore()
