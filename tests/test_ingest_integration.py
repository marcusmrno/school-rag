import json
import os
from pathlib import Path

import psycopg
import pytest

from core import config
from ingest.pipeline import ingest_dir

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://courselens:courselens@localhost:5432/courselens_test"
)
SCHEMA = Path(__file__).parent.parent / "db" / "01-schema.sql"
TEXT = "CHAPTER I.\n\nFirst paragraph about liberty.\n\nSecond paragraph about harm."
LICENSED = {
    "liberty.txt": {
        "title": "On Liberty",
        "source_url": "https://example.org/liberty",
        "license": "Public domain",
    }
}


@pytest.fixture
def conn():
    try:
        conn = psycopg.connect(TEST_DB, autocommit=True)
    except psycopg.OperationalError:
        pytest.skip("test DB not reachable; run `docker compose up -d --wait`")
    conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    conn.execute(SCHEMA.read_text())
    yield conn
    conn.close()


def fake_embed(texts):
    return [[0.0] * 1023 + [1.0] for _ in texts]


def make_corpus(directory, sources):
    (directory / "liberty.txt").write_text(TEXT)
    (directory / "slides.pdf").write_bytes(b"%PDF-not-supported-yet")
    (directory / "sources.json").write_text(json.dumps(sources))
    return directory


def test_ingests_document_and_chunks_with_metadata(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODE", "public")
    total, skipped = ingest_dir(conn, make_corpus(tmp_path, LICENSED), "PHIL", fake_embed)

    assert (total, skipped) == (1, [])
    assert conn.execute("SELECT title, license FROM documents").fetchall() == [
        ("On Liberty", "Public domain")
    ]
    course, location, content = conn.execute("SELECT course, location, content FROM chunks").fetchone()
    assert course == "PHIL"
    assert location == "CHAPTER I, ¶ 1–2"
    assert "harm" in content


def test_reingest_replaces_instead_of_duplicating(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODE", "public")
    corpus = make_corpus(tmp_path, LICENSED)
    ingest_dir(conn, corpus, "PHIL", fake_embed)
    ingest_dir(conn, corpus, "PHIL", fake_embed)

    assert conn.execute("SELECT count(*) FROM documents").fetchone() == (1,)
    assert conn.execute("SELECT count(*) FROM chunks").fetchone() == (1,)


def test_public_mode_skips_files_without_license(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODE", "public")
    total, skipped = ingest_dir(conn, make_corpus(tmp_path, {}), "PHIL", fake_embed)

    assert total == 0
    assert skipped == [("liberty.txt", "public mode requires a license in sources.json")]
    assert conn.execute("SELECT count(*) FROM documents").fetchone() == (0,)


def test_private_mode_allows_missing_license(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODE", "private")
    total, skipped = ingest_dir(conn, make_corpus(tmp_path, {}), "PHIL", fake_embed)

    assert (total, skipped) == (1, [])
    assert conn.execute("SELECT title FROM documents").fetchone() == ("liberty",)
