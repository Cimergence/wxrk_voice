from app.config import get_settings
from extraction.extract import run_extraction
from extraction.schema import REQUIRED_KEYS, validate_extraction
from providers import get_llm


async def test_extraction_returns_valid_schema(sample_transcript):
    data = await run_extraction(sample_transcript, get_llm(get_settings()))
    # Required keys all present
    for key in REQUIRED_KEYS:
        assert key in data
    # Does not raise
    validate_extraction(data)


async def test_extraction_recovers_numbers_and_skills(sample_transcript):
    data = await run_extraction(sample_transcript, get_llm(get_settings()))
    metric_values = " ".join(m["value"] for m in data["metrics"])
    assert "40%" in metric_values
    assert "2 million" in metric_values
    assert any(s.lower() == "python" for s in data["skills"])
    assert any(s.lower() in ("postgres", "postgresql") for s in data["skills"])


def test_validate_extraction_rejects_missing_keys():
    import pytest

    with pytest.raises(ValueError):
        validate_extraction({"role_summary": "x"})
