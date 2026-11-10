import contextlib

import anthropic
import httpx2
import psycopg
import pytest
from fastapi.testclient import TestClient

import api.main as main
from generate.answer import Answer
from retrieval.search import ScoredChunk


def chunk(i, content=None):
    return ScoredChunk(i, "On Liberty", f"CHAPTER I, ¶ {i}", "PHIL", None, content or f"text {i}", i, 0.5)


@pytest.fixture
def calls(monkeypatch):
    seen = []
    monkeypatch.setattr(main, "connect", lambda: contextlib.nullcontext())
    monkeypatch.setattr(main, "search", lambda *a, **kw: seen.append((a, kw)) or [chunk(1), chunk(2)])
    monkeypatch.setattr(main, "answer", lambda q, chunks: Answer("Only to prevent harm [2].", True, [2]))
    return seen


def post(body):
    return TestClient(main.app).post("/ask", json=body)


def test_ask_returns_answer_with_citations(calls):
    r = post({"question": "What is harm?"})
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["answer"] == "Only to prevent harm [2]."
    assert len(body["citations"]) == 1
    c = body["citations"][0]
    assert (c["n"], c["chunk_id"], c["location"]) == (2, 2, "CHAPTER I, ¶ 2")
    assert [h["vector_rank"] for h in body["debug"]["retrieved"]] == [1, 2]
    assert set(body["debug"]["retrieved"][0]) == {
        "chunk_id", "title", "location", "vector_rank", "vector_score", "keyword_rank", "keyword_score", "rrf"}
    assert set(body["debug"]["timings_ms"]) == {"search", "generate"}


def test_ask_passes_question_and_course_to_search(calls):
    post({"question": "  What is harm?  ", "course": "PHIL"})
    (args, _), = calls
    assert args[1:] == ("What is harm?", "PHIL")


def test_long_chunk_excerpt_is_truncated(calls, monkeypatch):
    monkeypatch.setattr(main, "search", lambda *a, **kw: [chunk(1, "a" * 400)])
    monkeypatch.setattr(main, "answer", lambda q, chunks: Answer("Yes [1].", True, [1]))
    r = post({"question": "q"})
    assert r.json()["citations"][0]["excerpt"] == "a" * 300 + "…"


def test_not_found_returns_message_and_no_citations(calls, monkeypatch):
    monkeypatch.setattr(main, "answer", lambda q, chunks: Answer("", False, []))
    body = post({"question": "q"}).json()
    assert body["answer"] == "I couldn't find this in the course material."
    assert body["citations"] == []
    assert body["found"] is False
    assert len(body["debug"]["retrieved"]) == 2


def test_not_found_returns_nearest_sources(calls, monkeypatch):
    monkeypatch.setattr(main, "search", lambda *a, **kw: [chunk(i) for i in range(1, 6)])
    monkeypatch.setattr(main, "answer", lambda q, chunks: Answer("", False, []))
    body = post({"question": "q"}).json()
    assert [s["n"] for s in body["nearest"]] == [1, 2, 3]
    assert body["nearest"][0]["location"] == "CHAPTER I, ¶ 1"
    assert set(body["nearest"][0]) == {
        "n", "chunk_id", "title", "location", "course", "source_url", "excerpt"}


def test_found_has_no_nearest(calls):
    assert post({"question": "q"}).json()["nearest"] == []


def test_retrieved_carries_title_and_location(calls):
    hit = post({"question": "q"}).json()["debug"]["retrieved"][0]
    assert (hit["title"], hit["location"]) == ("On Liberty", "CHAPTER I, ¶ 1")


def test_claude_failure_returns_503(calls, monkeypatch):
    def boom(q, chunks):
        raise anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))

    monkeypatch.setattr(main, "answer", boom)
    r = post({"question": "q"})
    assert r.status_code == 503
    assert "try again" in r.json()["detail"]


def test_db_down_returns_503(monkeypatch):
    def down():
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(main, "connect", down)
    assert post({"question": "q"}).status_code == 503


@pytest.mark.parametrize(
    "body",
    [{"question": "   "}, {"question": "x" * 501}, {"question": "hi", "course": "MATH"}, {}],
)
def test_rejects_bad_requests(calls, body):
    assert post(body).status_code == 422
    assert calls == []
