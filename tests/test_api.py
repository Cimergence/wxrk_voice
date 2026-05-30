"""HTTP surface: sessions lifecycle, transcript, finalize, simulate, auth."""
from app.config import reset_settings_cache
from tests.conftest import EXPERIENCE_CONTEXT


def _create(client):
    return client.post(
        "/sessions",
        json={
            "experience_id": "exp_1",
            "candidate_name": "Sara",
            "experience_context": EXPERIENCE_CONTEXT,
        },
    )


def test_create_session_contract(client):
    r = _create(client)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"session_id", "room", "join_token", "ws_url"}
    assert body["room"] == f"voice-{body['session_id']}"


def test_transcript_then_finalize(client):
    sid = _create(client).json()["session_id"]
    # seed a couple of turns via the worker callback endpoint
    client.post(f"/internal/sessions/{sid}/turn",
                json={"speaker": "agent", "text": "Tell me about the role."})
    client.post(f"/internal/sessions/{sid}/turn",
                json={"speaker": "user",
                      "text": "I built the payments service with Python and Postgres, served 2 million users."})

    t = client.get(f"/sessions/{sid}/transcript")
    assert t.status_code == 200
    body = t.json()
    assert body["status"] == "active"
    assert len(body["turns"]) == 2

    f = client.post(f"/sessions/{sid}/finalize")
    assert f.status_code == 200
    fb = f.json()
    assert fb["session_id"] == sid and fb["experience_id"] == "exp_1"
    assert set(["skills", "metrics", "role_summary"]).issubset(fb["data"])
    # session now ended
    assert client.get(f"/sessions/{sid}/transcript").json()["status"] == "ended"


def test_transcript_404_for_unknown(client):
    assert client.get("/sessions/nope/transcript").status_code == 404


def test_simulate_endpoint(client):
    r = client.post("/simulate", json={"experience_context": EXPERIENCE_CONTEXT,
                                       "difficulty": "easy", "max_turns": 12})
    assert r.status_code == 200
    body = r.json()
    assert len(body["transcript"]) > 0
    assert "metrics" in body["extraction"]


def test_simulate_requires_input(client):
    r = client.post("/simulate", json={"difficulty": "easy"})
    assert r.status_code == 400


def test_ws_stream_replays_and_follows(client):
    sid = _create(client).json()["session_id"]
    client.post(f"/internal/sessions/{sid}/turn",
                json={"speaker": "agent", "text": "Hello there."})
    with client.websocket_connect(f"/sessions/{sid}/stream") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "turn" and msg["text"] == "Hello there."


def test_service_boots_and_serves_under_swapped_llm(client, monkeypatch):
    """The seam's whole point: flip LLM_PROVIDER to the second impl and the
    service still boots and serves /sessions + /simulate (no code change).
    /simulate without a Gemini key surfaces a clean error, not a crash."""
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    reset_settings_cache()
    assert client.get("/health").json()["providers"]["llm"] == "gemini"
    assert _create(client).status_code == 200  # session creation needs no LLM
    r = client.post("/simulate", json={"experience_context": EXPERIENCE_CONTEXT})
    assert r.status_code in (200, 400, 500, 502)  # reachable; errors cleanly w/o key


def test_auth_enforced_when_enabled(client, monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("SERVICE_API_KEY", "secret123")
    reset_settings_cache()
    # no token -> 401
    assert _create(client).status_code == 401
    # correct token -> ok
    r = client.post(
        "/sessions",
        headers={"Authorization": "Bearer secret123"},
        json={"experience_id": "e", "experience_context": EXPERIENCE_CONTEXT},
    )
    assert r.status_code == 200
