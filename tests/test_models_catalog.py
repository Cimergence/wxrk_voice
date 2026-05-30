"""Per-run model choice + cost: catalog validation, key-gating, and that the
chosen model is what actually drives (and prices) the run."""
import pytest

from app.config import reset_settings_cache
from providers import catalog
from tests.conftest import EXPERIENCE_CONTEXT


# --- GET /llm/options: key-gated -------------------------------------------
def test_llm_options_lists_only_key_present_providers(client):
    body = client.get("/llm/options").json()
    assert body["convo"] and body["extract"]
    provs = {m["provider"] for m in body["convo"] + body["extract"]}
    # keys for openai + xai are provisioned in .env
    assert {"openai", "xai"}.issubset(provs)
    assert provs.issubset({"openai", "xai", "anthropic"})
    assert body["defaults"]["convo"] and body["defaults"]["extract"]


def test_llm_options_excludes_provider_without_key(client, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "")
    reset_settings_cache()
    body = client.get("/llm/options").json()
    provs = {m["provider"] for m in body["convo"] + body["extract"]}
    assert "xai" not in provs


# --- off-catalog rejection --------------------------------------------------
def test_simulate_rejects_off_catalog_model(client):
    r = client.post("/simulate", json={
        "experience_context": EXPERIENCE_CONTEXT, "difficulty": "easy", "max_turns": 8,
        "convo": {"provider": "openai", "model": "gpt-9000-imaginary"},
    })
    assert r.status_code == 400


def test_simulate_rejects_model_used_in_wrong_role(client):
    # gpt-5.4 is an extract-only model; using it for convo must be rejected.
    r = client.post("/simulate", json={
        "experience_context": EXPERIENCE_CONTEXT, "difficulty": "easy", "max_turns": 8,
        "convo": {"provider": "openai", "model": "gpt-5.4"},
    })
    assert r.status_code == 400


def test_create_session_rejects_off_catalog_model(client):
    r = client.post("/sessions", json={
        "experience_id": "e", "experience_context": EXPERIENCE_CONTEXT,
        "extract": {"provider": "xai", "model": "grok-nope"},
    })
    assert r.status_code == 400


# --- the chosen model is what actually runs (+ is priced) -------------------
def test_simulate_chosen_models_drive_cost(client):
    r = client.post("/simulate", json={
        "experience_context": EXPERIENCE_CONTEXT, "difficulty": "easy", "max_turns": 12,
        "convo": {"provider": "xai", "model": "grok-4.3"},
        "extract": {"provider": "openai", "model": "gpt-5.4-mini"},
    })
    assert r.status_code == 200
    cost = r.json()["cost"]
    assert cost["convo"]["model"] == "grok-4.3"
    assert cost["extract"]["model"] == "gpt-5.4-mini"
    assert cost["total_usd"] > 0
    assert cost["convo"]["in_tokens"] > 0 and cost["extract"]["in_tokens"] > 0


def test_changing_extract_model_changes_cost(client):
    """Same deterministic run, different extract model -> the chosen model's rate
    is what's actually applied, so a pricier model yields a higher cost."""
    base = {"experience_context": EXPERIENCE_CONTEXT, "difficulty": "easy", "max_turns": 12,
            "convo": {"provider": "xai", "model": "grok-4.3"}}
    cheap = client.post("/simulate", json={**base, "extract": {"provider": "openai", "model": "gpt-5.4-mini"}}).json()
    pricey = client.post("/simulate", json={**base, "extract": {"provider": "anthropic", "model": "claude-sonnet-4-6"}}).json()
    assert pricey["cost"]["extract"]["model"] == "claude-sonnet-4-6"
    # identical transcript (deterministic stub) but a dearer extractor costs more
    assert pricey["cost"]["extract"]["usd"] > cheap["cost"]["extract"]["usd"]


def test_omitted_choice_falls_back_to_default(client):
    r = client.post("/simulate", json={
        "experience_context": EXPERIENCE_CONTEXT, "difficulty": "easy", "max_turns": 8,
    })
    assert r.status_code == 200
    cost = r.json()["cost"]
    # default resolution picks a key-present catalog model for each role
    assert cost["convo"]["model_id"] in catalog.models()
    assert cost["extract"]["model_id"] in catalog.models()


# --- catalog unit checks ----------------------------------------------------
def test_validate_choice_unit():
    mi = catalog.validate_choice("convo", "xai", "grok-4.3")
    assert mi.id == "xai-grok-4.3"
    with pytest.raises(ValueError):
        catalog.validate_choice("convo", "openai", "gpt-5.4")  # extract-only
    with pytest.raises(ValueError):
        catalog.validate_choice("extract", "openai", "made-up")
