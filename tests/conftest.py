import json
from pathlib import Path

import pytest

from app.config import reset_settings_cache


@pytest.fixture(autouse=True)
def _clean_provider_env(monkeypatch):
    """Default every test to the offline stub providers; reset the cached
    Settings so per-test env overrides take effect."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("STT_PROVIDER", "stub")
    monkeypatch.setenv("TTS_PROVIDER", "stub")
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def sample_transcript():
    path = Path(__file__).parent / "fixtures" / "sample_transcript.json"
    return json.loads(path.read_text())


EXPERIENCE_CONTEXT = (
    "Senior Backend Engineer at Acme, 2021–2023. Built the payments service. "
    "Detected tech: Python, Postgres, Kafka, AWS."
)
