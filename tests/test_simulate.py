from app.config import get_settings
from app.models import SimulateRequest
from extraction.schema import validate_extraction
from providers import get_llm
from simulate.harness import run_simulation
from tests.conftest import EXPERIENCE_CONTEXT


async def _run(difficulty):
    req = SimulateRequest(
        experience_context=EXPERIENCE_CONTEXT, difficulty=difficulty, max_turns=16
    )
    return await run_simulation(req, get_llm(get_settings()))


async def test_both_difficulties_produce_valid_runs():
    for difficulty in ("easy", "hard"):
        res = await _run(difficulty)
        assert len(res.transcript) > 0, f"{difficulty} transcript empty"
        # alternates agent/user, every turn has speaker+text+ts
        assert res.transcript[0].speaker == "agent"
        assert all(t.text.strip() for t in res.transcript)
        validate_extraction(res.extraction)
        assert res.ground_truth is not None


async def test_easy_recovers_at_least_as_many_metrics_as_hard():
    easy = await _run("easy")
    hard = await _run("hard")
    easy_metrics = len(easy.extraction["metrics"])
    hard_metrics = len(hard.extraction["metrics"])
    assert easy_metrics >= hard_metrics
    assert easy_metrics > 0  # the happy path must recover something


async def test_simulate_accepts_ready_persona():
    persona = {
        "ground_truth": {
            "role": "ran the data platform",
            "scope": "team of 5, 1 million events a day",
            "skills": ["Python", "Spark", "Airflow"],
            "metrics": [{"claim": "throughput", "value": "1 million events", "before": None}],
            "achievements": ["built the pipeline"],
            "star_stories": [],
        }
    }
    req = SimulateRequest(persona=persona, difficulty="easy", max_turns=8)
    res = await run_simulation(req, get_llm(get_settings()))
    assert len(res.transcript) > 0
    validate_extraction(res.extraction)
