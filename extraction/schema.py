"""Extraction output schema (from operation_files/PROMPT.md) + validation."""
from __future__ import annotations

from jsonschema import Draft7Validator

REQUIRED_KEYS = [
    "role_summary", "scope", "skills", "metrics",
    "achievements", "star_stories", "quotes", "gaps",
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
        "gaps": {"type": "array", "items": {"type": "string"}},
    },
}

_validator = Draft7Validator(EXTRACTION_SCHEMA)


def validate_extraction(data: dict) -> None:
    """Raise jsonschema.ValidationError if `data` doesn't match the schema."""
    errors = sorted(_validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])
        raise ValueError(f"Extraction JSON failed schema validation: {msgs}")
