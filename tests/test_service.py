"""Тесты служебных эндпоинтов: health, metrics, статистика, обработка отказа БД."""
from app.db import Database
from app.main import create_app


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["database"] == "up"


def test_health_when_db_down(monkeypatch):
    monkeypatch.setenv("SKIP_DB_INIT", "1")
    broken = Database("sqlite:////nonexistent-dir/x.db")
    app = create_app(broken)
    r = app.test_client().get("/health")
    assert r.status_code == 503
    assert r.get_json()["status"] == "degraded"


def test_metrics_format(client, student):
    client.get("/api/students")
    text = client.get("/metrics").get_data(as_text=True)
    assert "grades_http_requests_total" in text
    assert "grades_db_up 1" in text
    assert "grades_students 1" in text


def test_stats(client, student, disciplines):
    client.post("/api/grades", json={"student_id": student["id"], "discipline_id": disciplines[0]["id"], "score": 80})
    s = client.get("/api/stats").get_json()
    assert s == {"students": 1, "disciplines": 2, "grades": 1, "average_score": 80.0}


def test_request_id_header(client):
    r = client.get("/", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


def test_unknown_route(client):
    assert client.get("/nope").status_code == 404
