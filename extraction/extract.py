"""Turn a transcript into validated structured CV data via the extraction prompt."""
from __future__ import annotations

import json
from typing import Iterable

from agent.prompts import extraction_prompt
from extraction.schema import REQUIRED_KEYS, validate_extraction
from providers.base import LLMProvider


def format_transcript(turns: Iterable) -> str:
    """Render turns (Turn models or dicts) as 'speaker: text' lines."""
    lines = []
    for t in turns:
        speaker = getattr(t, "speaker", None) or (t.get("speaker") if isinstance(t, dict) else None)
        text = getattr(t, "text", None) or (t.get("text") if isinstance(t, dict) else None)
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def parse_llm_json(raw: str) -> dict:
    """Robustly parse JSON that an LLM may have wrapped in prose or ``` fences."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(s)):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start : i + 1])
                    except json.JSONDecodeError:
                        break
        start = s.find("{", start + 1)
    raise ValueError(f"Could not parse JSON from LLM output: {raw[:200]!r}")


def _coerce(data: dict) -> dict:
    """Fill any missing required keys so partial LLM output still validates."""
    defaults = {
        "role_summary": None, "scope": None, "skills": [], "metrics": [],
        "achievements": [], "star_stories": [], "quotes": [],
        "emotional_context": None, "gaps": [],
    }
    for k in REQUIRED_KEYS:
        data.setdefault(k, defaults[k])
    return data


async def run_extraction(turns: Iterable, llm: LLMProvider) -> dict:
    prompt = extraction_prompt(format_transcript(turns))
    raw = await llm.complete(prompt, [], temperature=0.0)
    data = _coerce(parse_llm_json(raw))
    validate_extraction(data)
    return data
