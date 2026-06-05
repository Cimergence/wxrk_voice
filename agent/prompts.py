"""Single source of truth for prompts: parse them out of
``operation_files/PROMPT.md`` so the running service uses the exact text the
spec defines. Blocks are classified by content (robust to reordering), not by
position.

Exposes:
    live_interview_prompt(experience_context) -> str
    extraction_prompt(transcript_text)        -> str
    candidate_prompt(persona, difficulty)     -> str
    persona_generator_prompt(experience_context) -> str
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_PROMPT_FILE = Path(__file__).resolve().parent.parent / "operation_files" / "PROMPT.md"

_FENCE_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)


@lru_cache
def _blocks() -> list[str]:
    """All fenced code blocks in PROMPT.md, with blockquote markers stripped so
    the indented easy/hard mode blocks are captured too."""
    raw = _PROMPT_FILE.read_text(encoding="utf-8")
    # Strip leading "> " (blockquote) from every line so quoted fences parse.
    dequoted = "\n".join(re.sub(r"^> ?", "", line) for line in raw.splitlines())
    return [m.group(1).strip("\n") for m in _FENCE_RE.finditer(dequoted)]


def _find(*must_contain: str, must_not: tuple[str, ...] = ()) -> str:
    for block in _blocks():
        if all(s in block for s in must_contain) and not any(s in block for s in must_not):
            return block
    raise RuntimeError(
        f"No PROMPT.md block contains all of {must_contain!r} (excluding {must_not!r}). "
        "operation_files/PROMPT.md may have changed shape."
    )


@lru_cache
def _live_template() -> str:
    return _find("You are Mira", "{{EXPERIENCE_CONTEXT}}")


@lru_cache
def _extraction_template() -> str:
    return _find("{{TRANSCRIPT}}", "structured CV data")


@lru_cache
def _candidate_template() -> str:
    return _find("{{CANDIDATE_PERSONA}}", "{{DIFFICULTY_MODE}}")


@lru_cache
def _persona_template() -> str:
    # Persona generator also carries {{EXPERIENCE_CONTEXT}}; disambiguate from the
    # live prompt via the "ground_truth" schema and exclude Mira.
    return _find("{{EXPERIENCE_CONTEXT}}", "ground_truth", must_not=("You are Mira",))


@lru_cache
def _difficulty_blocks() -> tuple[str, str]:
    # Phrases unique to each behaviour-mode block (not the candidate template,
    # which also mentions the word "forthcoming").
    easy = _find("forthcoming and organized")
    hard = _find("modest and a little vague")
    return easy, hard


def live_interview_prompt(experience_context: str) -> str:
    return _live_template().replace("{{EXPERIENCE_CONTEXT}}", experience_context.strip())


def extraction_prompt(transcript_text: str) -> str:
    return _extraction_template().replace("{{TRANSCRIPT}}", transcript_text.strip())


def persona_generator_prompt(experience_context: str) -> str:
    return _persona_template().replace("{{EXPERIENCE_CONTEXT}}", experience_context.strip())


def candidate_prompt(persona_json: str, difficulty: str) -> str:
    easy, hard = _difficulty_blocks()
    mode = easy if difficulty == "easy" else hard
    return (
        _candidate_template()
        .replace("{{CANDIDATE_PERSONA}}", persona_json.strip())
        .replace("{{DIFFICULTY_MODE}}", mode.strip())
    )
