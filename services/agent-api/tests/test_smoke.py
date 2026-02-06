from starlette.testclient import TestClient

from app.main import app


def test_health_ok() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ws_roundtrip() -> None:
    """WS returns session_id, request_id, answer_text, citations, addon (no echo)."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(
            {
                "session_id": "s1",
                "request_id": "r1",
                "user_query": "dicas para evitar filas no Magic Kingdom",
            }
        )
        resp = ws.receive_json()

        assert resp["session_id"] == "s1"
        assert resp["request_id"] == "r1"
        assert "answer_text" in resp
        assert isinstance(resp.get("citations"), list)
        assert "addon" in resp
