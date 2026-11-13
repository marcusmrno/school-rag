from types import SimpleNamespace

import pytest
from pytest import approx

from core.db import to_vector
import evals.run as er
from evals.run import first_gold_rank, normalize, resolve_gold, summarize

PROSE = "Society may restrict liberty only to prevent harm to others."
SLIDE = "Loops\nfor i in\u00a0range(3):\n    print(i)"


def rec(answerable=True, rank=None, **extra):
    return {"id": "q", "course": "PHIL", "answerable": answerable, "rank": rank,
            "search_ms": 10, "total_ms": 1000, **extra}


def test_normalize_collapses_whitespace_and_case():
    assert normalize("  The ONLY\n purpose\tfor ") == "the only purpose for"


def test_first_gold_rank():
    assert first_gold_rank([7, 3, 9], {9, 3}) == 2
    assert first_gold_rank([7], {1}) is None
    assert first_gold_rank([], {1}) is None


def test_summarize_retrieval_only():
    recs = [rec(rank=1), rec(rank=2), rec(rank=None), rec(answerable=False, rank=None)]
    s = summarize(recs)
    assert s["hit_at_5"] == approx(2 / 3)  # unanswerable excluded
    assert s["mrr"] == approx((1 + 0.5 + 0) / 3)
    assert s["citation"] is None and s["refusal"] is None


def test_summarize_with_answers():
    recs = [rec(rank=1, found=True, cited_gold=True), rec(rank=1, found=False, cited_gold=False),
            rec(answerable=False, found=False), rec(answerable=False, found=True)]
    s = summarize(recs)
    assert s["citation"] == approx(0.5)  # refused answerable counts as wrong
    assert s["refusal"] == approx(0.5)


@pytest.fixture
def corpus(conn):
    for name, text in [("harm.txt", PROSE), ("code.txt", SLIDE)]:
        doc = conn.execute(
            "INSERT INTO documents (course, title, source_path) VALUES ('PHIL', %s, %s) RETURNING id",
            (name, name),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO chunks (document_id, course, content_type, location, content, token_count, embedding)"
            " VALUES (%s, 'PHIL', 'prose', 'x', %s, 1, %s::vector)",
            (doc, text, to_vector([0.0] * 1024)),
        )
    return conn


def test_resolve_gold_matches_across_line_breaks(corpus):
    # slide content keeps newlines and indentation; the quote is written on one line
    ids = resolve_gold(corpus, [{"title": "code.txt", "quote": "for i in range(3): print(i)"}])
    assert len(ids) == 1


def test_resolve_gold_raises_on_no_match(corpus):
    with pytest.raises(ValueError, match="not in the corpus"):
        resolve_gold(corpus, [{"title": "harm.txt", "quote": "not in the corpus"}])


def test_resolve_gold_raises_on_too_many_matches(corpus):
    for i in range(3):  # 3 more "harm.txt" chunks -> 4 matches for the same quote
        doc = corpus.execute("SELECT id FROM documents WHERE title = 'harm.txt'").fetchone()[0]
        corpus.execute(
            "INSERT INTO chunks (document_id, course, content_type, location, content, token_count, embedding)"
            " VALUES (%s, 'PHIL', 'prose', 'x', %s, 1, %s::vector)",
            (doc, PROSE, to_vector([0.0] * 1024)),
        )
    with pytest.raises(ValueError, match="matches 4 chunks"):
        resolve_gold(corpus, [{"title": "harm.txt", "quote": "prevent harm"}])


def test_summarize_empty_group_is_none():
    s = summarize([rec(answerable=False, found=False)])
    assert s["hit_at_5"] is None and s["mrr"] is None and s["citation"] is None
    assert s["refusal"] == approx(1.0)


def test_run_config_records_with_answers(monkeypatch):
    chunks = [SimpleNamespace(chunk_id=1), SimpleNamespace(chunk_id=2)]
    seen = []
    monkeypatch.setattr(er, "search", lambda conn, query, **kw: seen.append(kw) or chunks)
    monkeypatch.setattr(er.anthropic, "Anthropic", lambda **kw: None)  # no key needed
    monkeypatch.setattr(
        er, "answer", lambda q, c, client: SimpleNamespace(found=True, cited=[1] if q == "a" else [2])
    )
    qs = [{"id": "a", "course": "PHIL", "question": "a", "gold": [{}]},
          {"id": "b", "course": "PHIL", "question": "b", "gold": [{}]}]
    recs = er.run_config(None, "vector", qs, {"a": {1}, "b": {1}}, answers=True)
    assert [r["cited_gold"] for r in recs] == [True, False]
    assert [r["rank"] for r in recs] == [1, 1]
    assert set(recs[0]) == {"id", "course", "answerable", "rank", "search_ms", "found", "cited_gold", "total_ms"}
    assert all(kw == er.CONFIGS["vector"] for kw in seen)  # no course filter
