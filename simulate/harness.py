"""Text-mode simulation: interviewer-LLM ↔ candidate-LLM, then extraction.

No audio. One LLM plays Mira (from the live interview prompt), another plays the
candidate (from the candidate-simulator prompt with the chosen difficulty block).
Used by POST /simulate for fast, key-free, end-to-end testing and prompt tuning.
"""
from __future__ import annotations

import json
from typing import Optional

from agent.prompts import (
    candidate_prompt,
    live_interview_prompt,
    persona_generator_prompt,
)
from app.models import SimulateRequest, SimulateResponse, Turn
from extraction.extract import parse_llm_json, run_extraction
from providers.base import ChatMessage, LLMProvider

_END_MARKERS = ("all set", "i'm all set", "im all set")


def _context_from_persona(persona: dict) -> str:
    gt = persona.get("ground_truth", {}) if isinstance(persona, dict) else {}
    role = gt.get("role", "a past role")
    scope = gt.get("scope", "")
    skills = ", ".join(gt.get("skills", []) or [])
    return f"{role}. {scope}. Detected tech: {skills}".strip()


async def run_simulation(req: SimulateRequest, llm: LLMProvider) -> SimulateResponse:
    if not req.persona and not req.experience_context:
        raise ValueError("Provide either `experience_context` or `persona`.")

    # 1) persona / ground truth
    if req.persona:
        persona = req.persona
    else:
        raw = await llm.complete(persona_generator_prompt(req.experience_context), [], temperature=0.4)
        persona = parse_llm_json(raw)
    ground_truth: Optional[dict] = persona.get("ground_truth") if isinstance(persona, dict) else None

    experience_context = req.experience_context or _context_from_persona(persona)
    live_system = live_interview_prompt(experience_context)
    cand_system = candidate_prompt(json.dumps(persona), req.difficulty)

    # 2) interviewer ↔ candidate loop
    transcript: list[Turn] = []
    interviewer_msgs: list[ChatMessage] = []   # POV: assistant = Mira's questions
    candidate_msgs: list[ChatMessage] = []     # POV: assistant = candidate's answers
    ts = 0
    for _ in range(max(1, req.max_turns)):
        question = await llm.complete(live_system, interviewer_msgs, temperature=0.5)
        transcript.append(Turn(speaker="agent", text=question, ts=ts)); ts += 1
        interviewer_msgs.append(ChatMessage("assistant", question))
        candidate_msgs.append(ChatMessage("user", question))
        if any(m in question.lower() for m in _END_MARKERS):
            break

        answer = await llm.complete(cand_system, candidate_msgs, temperature=0.7)
        transcript.append(Turn(speaker="user", text=answer, ts=ts)); ts += 1
        candidate_msgs.append(ChatMessage("assistant", answer))
        interviewer_msgs.append(ChatMessage("user", answer))

    # 3) extraction over the produced transcript
    extraction = await run_extraction(transcript, llm)

    return SimulateResponse(
        transcript=transcript,
        extraction=extraction,
        ground_truth=ground_truth,
    )
