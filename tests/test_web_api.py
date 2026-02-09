from fastapi.testclient import TestClient

from chatbot.web_api import web_api


def test_api_action_port_save_supported(monkeypatch):
    monkeypatch.delenv("WEB_API_TOKEN", raising=False)
    client = TestClient(web_api)

    response = client.post("/api/action", json={"user_id": 123, "action": "port:save"})
    assert response.status_code == 200
    payload = response.json()
    assert "text" in payload
    assert "buttons" in payload
