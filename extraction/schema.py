"""Extraction output schema (from operation_files/PROMPT.md) + validation."""
from __future__ import annotations

from jsonschema import Draft7Validator

REQUIRED_KEYS = [
    "role_summary", "scope", "skills", "metrics",
    "achievements", "star_stories", "quotes", "emotional_context", "gaps",
]

EXTRACTION_SCHEMA = {
    "type": "object",
    "required": REQUIRED_KEYS,
    "properties": {
        "role_summary": {"type": ["string", "null"]},
        "scope": {"type": ["string", "null"]},
        "skills": {"type": "array", "items": {"type": "string"}},
        "metrics": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["claim", "value", "before"],
                "properties": {
                    "claim": {"type": ["string", "null"]},
                    "value": {"type": ["string", "null"]},
                    "before": {"type": ["string", "null"]},
                },
            },
        },
        "achievements": {"type": "array", "items": {"type": "string"}},
        "star_stories": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["situation", "task", "action", "result"],
                "properties": {
                    "situation": {"type": ["string", "null"]},
                    "task": {"type": ["string", "null"]},
                    "action": {"type": ["string", "null"]},
                    "result": {"type": ["string", "null"]},
                },
            },
        },
        "quotes": {"type": "array", "items": {"type": "string"}},
        "emotional_context": {"type": ["string", "null"]},
        "gaps": {"type": "array", "items": {"type": "string"}},
    },
}

_validator = Draft7Validator(EXTRACTION_SCHEMA)

_GENERIC_EMOTIONAL = {"not captured", "not mentioned", "unclear", "n/a", ""}


def _auto_gaps(data: dict) -> list[str]:
    """Derive gaps that the LLM prompt mandates but may have missed."""
    auto: list[str] = []
    if len(data.get("metrics", [])) < 2:
        auto.append("No quantified metrics — recruiter will ask for numbers")
    stars = data.get("star_stories", [])
    complete = [
        s for s in stars
        if all(s.get(k) for k in ("situation", "task", "action", "result"))
    ]
    if not complete:
        auto.append("Incomplete STAR story — situation/task/action/result not all captured")
    if len(data.get("skills", [])) < 2:
        auto.append("Too few skills named — clarify tech stack")
    if not data.get("quotes"):
        auto.append("No memorable quotes — candidate's own words missing")
    ec = (data.get("emotional_context") or "").strip().lower()
    if not ec or ec in _GENERIC_EMOTIONAL or len(ec) < 20:
        auto.append("Emotional context unclear — what they owned emotionally not established")
    return auto


def validate_extraction(data: dict) -> None:
    """Validate schema and backfill any gaps the LLM should have flagged."""
    errors = sorted(_validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])
        raise ValueError(f"Extraction JSON failed schema validation: {msgs}")
    existing = set(data.get("gaps", []))
    for gap in _auto_gaps(data):
        if not any(gap[:30] in g for g in existing):
            data["gaps"].append(gap)
