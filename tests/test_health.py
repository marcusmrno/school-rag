import psycopg
from fastapi.testclient import TestClient

import api.main as main


class FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        return None


def test_health_ok_when_db_reachable(monkeypatch):
    monkeypatch.setattr(main, "connect", lambda: FakeConn())
    r = TestClient(main.app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_503_when_db_down(monkeypatch):
    def down():
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(main, "connect", down)
    r = TestClient(main.app).get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "db unreachable"}
