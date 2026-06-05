def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body["providers"]) == {"llm", "stt", "tts"}


def test_test_page_served(client):
    r = client.get("/test")
    assert r.status_code == 200
    assert "Simulate" in r.text and "Start" in r.text
