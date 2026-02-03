from fastapi.testclient import TestClient
from app.main import app

def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_retrieve_stub_shape():
    c = TestClient(app)
    r = c.post("/retrieve_product_candidates", json={"query": "teste", "debug": True})
    assert r.status_code == 200
    body = r.json()
    assert "candidates" in body
