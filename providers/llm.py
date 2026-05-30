"""LLM implementations.

* GeminiLLM — hosted default (Gemini 2.5 Flash Lite) over the REST API via httpx,
  so it needs only an API key, no heavy SDK. This is what production runs.
* StubLLM — a fully offline, deterministic "interview engine". It role-plays
  interviewer, candidate, persona generator and extractor by recognising which
  fixed prompt (from operation_files/PROMPT.md) it was handed. Lets /simulate,
  finalize and the whole test suite run with zero API keys.
"""
from __future__ import annotations

import json
import re
from typing import Sequence

import httpx

from app.config import Settings
from providers.base import ChatMessage, LLMProvider


# --------------------------------------------------------------------------- #
# Hosted: Gemini over REST
# --------------------------------------------------------------------------- #
class GeminiLLM(LLMProvider):
    name = "gemini"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.gemini_model

    async def complete(
        self,
        system: str,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.6,
        max_tokens: int | None = None,
    ) -> str:
        if not self.settings.gemini_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=gemini but GEMINI_API_KEY is unset. "
                "Set the key or switch LLM_PROVIDER=stub."
            )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        contents = [
            {
                "role": "model" if m.role == "assistant" else "user",
                "parts": [{"text": m.content}],
            }
            for m in messages
        ]
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents or [{"role": "user", "parts": [{"text": "Begin."}]}],
            "generationConfig": {
                "temperature": temperature,
                **({"maxOutputTokens": max_tokens} if max_tokens else {}),
            },
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url, params={"key": self.settings.gemini_api_key}, json=body
            )
            resp.raise_for_status()
            data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# --------------------------------------------------------------------------- #
# Offline: deterministic stub engine
# --------------------------------------------------------------------------- #
_NUM = r"\d[\d,\.]*"
_UNIT = (
    r"(?:%|percent|million|billion|thousand|k\b|users|customers|people|engineers|"
    r"developers|requests|rps|qps|ms|seconds|sec|minutes|hours|days|x\b|\$|gb|tb)"
)
_METRIC_RE = re.compile(rf"{_NUM}\s*{_UNIT}", re.IGNORECASE)

_TECH_WORDS = [
    "Python", "Django", "FastAPI", "Postgres", "PostgreSQL", "Kafka", "AWS",
    "Redis", "Docker", "Kubernetes", "React", "TypeScript", "Go", "Java",
    "Terraform", "GraphQL", "Celery", "Spark", "Airflow", "Snowflake",
]

# Mira's scripted interview. Probe questions force the guarded candidate to reveal.
_INTERVIEW_SCRIPT = [
    "Hi there — I'd love to dig into this experience with you. "
    "Walk me through what you actually did day to day.",
    "Nice. Roughly how many people were on the team with you?",          # probe
    "Got it. And what kind of scale were you at — how many users or how much volume?",  # probe
    "What did that number look like before you came in?",                 # probe
    "What were the main tools and tech you leaned on there?",
    "What's the one thing you're proudest of, and what changed because of it?",
    "Walk me through one situation start to finish — the problem, "
    "what you did, and how it turned out.",
]
_CLOSING = (
    "So to recap: you owned a real piece of work, used solid tech, and moved real "
    "numbers — thanks for that, I'm all set."
)
_PROBE_WORDS = ("how many", "how much", "number", "users", "volume",
                "before", "scale", "size", "percent")


def _extract_first_json(text: str) -> dict:
    """Pull the first balanced {...} object out of a larger string."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return {}


def _find_metrics(text: str) -> list[str]:
    seen: list[str] = []
    for m in _METRIC_RE.finditer(text):
        v = re.sub(r"\s+", " ", m.group(0).strip().rstrip("."))
        if v.lower() not in {s.lower() for s in seen}:
            seen.append(v)
    return seen


class StubLLM(LLMProvider):
    name = "stub"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def complete(
        self,
        system: str,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.6,
        max_tokens: int | None = None,
    ) -> str:
        if "structured CV data" in system and "Schema:" in system:
            return self._extract(system)
        if "believable candidate persona" in system:
            return self._persona(system)
        if "role-playing a real job candidate" in system:
            return self._candidate(system, messages)
        if "You are Mira" in system:
            return self._interviewer(messages)
        # Unknown prompt: echo a short neutral reply so callers never crash.
        return "Okay."

    # -- role: interviewer (Mira) -----------------------------------------
    def _interviewer(self, messages: Sequence[ChatMessage]) -> str:
        asked = sum(1 for m in messages if m.role == "assistant")
        if asked < len(_INTERVIEW_SCRIPT):
            return _INTERVIEW_SCRIPT[asked]
        return _CLOSING

    # -- role: candidate ---------------------------------------------------
    def _candidate(self, system: str, messages: Sequence[ChatMessage]) -> str:
        persona = _extract_first_json(system)
        gt = persona.get("ground_truth", {}) if isinstance(persona, dict) else {}
        metrics = [m.get("value", "") for m in gt.get("metrics", []) if m.get("value")]
        skills = gt.get("skills", []) or []
        stars = gt.get("star_stories", []) or []
        role = gt.get("role", "owned a real chunk of the work")

        easy = "forthcoming and organized" in system  # phrase unique to the easy block
        last_q = messages[-1].content.lower() if messages else ""
        prior = " ".join(m.content for m in messages if m.role == "assistant")
        unrevealed = [v for v in metrics if v.lower() not in prior.lower()]
        is_probe = any(w in last_q for w in _PROBE_WORDS)
        wants_story = "situation" in last_q or "start to finish" in last_q

        if easy:
            if not prior:  # opening answer: volunteer everything up front
                bits = [f"Sure — I {role}."]
                if metrics:
                    bits.append("To give you the numbers: " + ", ".join(metrics) + ".")
                if skills:
                    bits.append("Mostly worked with " + ", ".join(skills[:4]) + ".")
                return " ".join(bits)
            if wants_story and stars:
                s = stars[0]
                return (
                    f"{s.get('situation','')} {s.get('task','')} "
                    f"{s.get('action','')} {s.get('result','')}".strip()
                )
            if "tool" in last_q or "tech" in last_q:
                return "We leaned on " + ", ".join(skills[:5]) + "." if skills else \
                    "A pretty standard modern stack, honestly."
            return "Yeah, happy to expand — it was a good stretch of work for me."

        # hard / guarded
        if is_probe and unrevealed:
            return f"Hmm, let me think — it was {unrevealed[0]}, roughly."
        if wants_story and stars and is_probe:
            s = stars[0]
            return f"{s.get('situation','')} {s.get('action','')} {s.get('result','')}".strip()
        if "tool" in last_q or "tech" in last_q:
            return "Oh, the usual — " + (", ".join(skills[:2]) if skills else "nothing fancy") + "."
        return "Honestly I just kept things running and tried to do right by the team."

    # -- role: persona generator ------------------------------------------
    def _persona(self, system: str) -> str:
        # Isolate the injected experience context — it sits between the
        # "Experience summary:" label and the prompt's own "Schema:" section.
        ctx = system.split("Experience summary:")[-1].split("Schema:")[0]
        detected = []
        if "Detected tech:" in ctx:
            tail = ctx.split("Detected tech:")[-1]
            detected = [t.strip(" .\n") for t in re.split(r"[,\n]", tail) if t.strip(" .\n")][:6]
        if not detected:
            detected = [w for w in _TECH_WORDS if w.lower() in ctx.lower()][:5]
        if not detected:
            detected = ["Python", "Postgres", "AWS"]
        persona = {
            "persona_voice": "Speaks plainly, a little modest, warms up when asked specifics.",
            "ground_truth": {
                "role": "owned the core service end to end",
                "scope": "a team of 8 engineers, serving about 2 million users",
                "skills": detected,
                "metrics": [
                    {"claim": "latency improvement", "value": "around 40% faster",
                     "before": "about 800ms"},
                    {"claim": "scale served", "value": "about 2 million users",
                     "before": None},
                    {"claim": "team size", "value": "a team of 8 engineers",
                     "before": None},
                ],
                "achievements": [
                    "cut checkout failures dramatically after re-architecting the pipeline",
                    "launched the new service that became the team's backbone",
                ],
                "star_stories": [
                    {
                        "situation": "We had payment outages spiking every week.",
                        "task": "I was asked to stabilise the whole pipeline.",
                        "action": "I re-architected it around a queue with idempotent retries.",
                        "result": "It came out around 40% faster with far fewer failures.",
                    }
                ],
            },
        }
        return json.dumps(persona)

    # -- role: extractor ---------------------------------------------------
    def _extract(self, system: str) -> str:
        transcript = system.split("Transcript:")[-1]
        user_lines = [
            ln.split(":", 1)[1].strip()
            for ln in transcript.splitlines()
            if ln.lower().startswith(("user:", "candidate:"))
        ]
        user_text = " ".join(user_lines)
        metric_vals = _find_metrics(user_text)
        skills = [w for w in _TECH_WORDS if re.search(rf"\b{re.escape(w)}\b", transcript, re.I)]
        # de-dup skills case-insensitively, keep first spelling
        seen, uniq_skills = set(), []
        for s in skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                uniq_skills.append(s)

        data = {
            "role_summary": (user_lines[0][:160] if user_lines else None),
            "scope": next((ln for ln in user_lines if re.search(r"team|users|engineers", ln, re.I)), None),
            "skills": uniq_skills,
            "metrics": [{"claim": "reported figure", "value": v, "before": None} for v in metric_vals],
            "achievements": [
                ln for ln in user_lines
                if re.search(r"launch|cut|built|reduced|grew|saved|shipped|improv", ln, re.I)
            ][:4],
            "star_stories": (
                [{"situation": "", "task": "", "action": "",
                  "result": next((ln for ln in user_lines if _METRIC_RE.search(ln)), "")}]
                if metric_vals else []
            ),
            "quotes": [ln for ln in user_lines if len(ln) <= 120][:2],
            "gaps": [],
        }
        return json.dumps(data)
