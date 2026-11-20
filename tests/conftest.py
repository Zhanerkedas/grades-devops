import os

import pytest

from app.db import Database
from app.main import create_app


@pytest.fixture
def db(tmp_path):
    """SQLite во временном файле, либо PostgreSQL, если задан TEST_DATABASE_URL (в CI)."""
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    database.init_schema()
    yield database
    if database.kind == "postgres":
        with database.transaction() as cur:
            cur.execute("TRUNCATE grades, students, disciplines RESTART IDENTITY CASCADE")


@pytest.fixture
def client(db):
    app = create_app(db)
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def student(client):
    return client.post("/api/students", json={
        "full_name": "Тестова Айгерим", "email": "aigerim@example.com", "group_name": "CSE-22"
    }).get_json()


@pytest.fixture
def disciplines(client):
    return [
        client.post("/api/disciplines", json={"title": "DevOps", "credits": 5}).get_json(),
        client.post("/api/disciplines", json={"title": "Базы данных", "credits": 3}).get_json(),
    ]
