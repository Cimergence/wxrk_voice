import pytest

from app.config import get_settings
from extraction.extract import run_extraction
from extraction.schema import REQUIRED_KEYS, validate_extraction
from providers import get_llm


async def test_extraction_returns_valid_schema(sample_transcript):
    data = await run_extraction(sample_transcript, get_llm(get_settings()))
    for key in REQUIRED_KEYS:
        assert key in data
    validate_extraction(data)


async def test_extraction_recovers_numbers_and_skills(sample_transcript):
    data = await run_extraction(sample_transcript, get_llm(get_settings()))
    metric_values = " ".join(m["value"] for m in data["metrics"])
    assert "40%" in metric_values
    assert "2 million" in metric_values
    assert any(s.lower() == "python" for s in data["skills"])
    assert any(s.lower() in ("postgres", "postgresql") for s in data["skills"])


async def test_extraction_includes_emotional_context(sample_transcript):
    data = await run_extraction(sample_transcript, get_llm(get_settings()))
    assert "emotional_context" in data


def test_validate_extraction_rejects_missing_keys():
    with pytest.raises(ValueError):
        validate_extraction({"role_summary": "x"})


def test_auto_gaps_fires_on_incomplete_extraction():
    # Minimal extraction that passes schema but is data-poor
    data = {
        "role_summary": "Engineer",
        "scope": "small team",
        "skills": ["Python"],
        "metrics": [],
        "achievements": [],
        "star_stories": [{"situation": "s", "task": "", "action": "", "result": ""}],
        "quotes": [],
        "emotional_context": None,
        "gaps": [],
    }
    validate_extraction(data)
    gaps = data["gaps"]
    assert any("metric" in g.lower() for g in gaps), "should flag missing metrics"
    assert any("STAR" in g for g in gaps), "should flag incomplete STAR"
    assert any("skill" in g.lower() for g in gaps), "should flag too few skills"
    assert any("quote" in g.lower() for g in gaps), "should flag missing quotes"
    assert any("emotional" in g.lower() for g in gaps), "should flag missing emotional context"


def test_auto_gaps_silent_on_complete_extraction():
    data = {
        "role_summary": "Payments tech lead",
        "scope": "8 engineers, 2M transactions/month",
        "skills": ["Python", "Postgres", "Kafka", "AWS"],
        "metrics": [
            {"claim": "incidents", "value": "0 over 6 months", "before": "4-8/month"},
            {"claim": "latency", "value": "120ms", "before": "800ms"},
        ],
        "achievements": ["Rebuilt payments pipeline", "Zero incidents for 6 months"],
        "star_stories": [{
            "situation": "Payments were failing weekly",
            "task": "Stabilise the pipeline without downtime",
            "action": "Rebuilt on Kafka with idempotent retries",
            "result": "Zero incidents for 6 months, P99 latency 800ms to 120ms",
        }],
        "quotes": ["The team started volunteering for payments features after the rebuild."],
        "emotional_context": "Proudest of the cultural shift — engineers went from scared to eager.",
        "gaps": [],
    }
    validate_extraction(data)
    assert not data["gaps"], f"should be gap-free, got: {data['gaps']}"
