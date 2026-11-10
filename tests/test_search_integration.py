import pytest
from pytest import approx

from core.embeddings import embed_documents
from ingest.pipeline import ingest_file
import retrieval.search as rs
from retrieval.search import search

HARM = (
    "CHAPTER I.\n\nSociety may restrict a person's liberty only to stop them from "
    "harming other people. Their own good, physical or moral, is not reason enough."
)
RECURSION = (
    "LECTURE 3.\n\nA recursive function calls itself on a smaller input until it "
    "reaches a base case, which returns without recursing."
)


@pytest.fixture
def corpus(conn, tmp_path):
    for name, text, course in [("harm.txt", HARM, "PHIL"), ("recursion.txt", RECURSION, "CPSC")]:
        path = tmp_path / name
        path.write_text(text)
        ingest_file(conn, path, course, {"title": name, "license": "test"}, embed_documents)
    return conn


def test_relevant_chunk_ranks_first(corpus):
    results = search(corpus, "When can the state interfere with someone's freedom?")
    assert [r.title for r in results] == ["harm.txt", "recursion.txt"]
    assert [r.vector_rank for r in results] == [1, 2]
    assert results[0].vector_score > results[1].vector_score
    assert results[0].course == "PHIL" and "liberty" in results[0].content


def test_course_filter(corpus):
    results = search(corpus, "When can the state interfere with someone's freedom?", course="CPSC")
    assert [r.title for r in results] == ["recursion.txt"]


def test_course_with_no_chunks_returns_empty(corpus):
    assert search(corpus, "What is a base case?", course="ENGL") == []


def test_k_limits_results(corpus):
    assert len(search(corpus, "What is a base case?", k=1)) == 1


def recursion_like(texts):  # stub query embedding: always the recursion text's vector
    return embed_documents([RECURSION])


def test_keyword_match_adds_keyword_rank(corpus):
    results = search(corpus, "harm")
    assert [r.title for r in results] == ["harm.txt", "recursion.txt"]
    assert results[0].keyword_rank == 1 and results[0].keyword_score > 0
    assert results[1].keyword_rank is None and results[1].keyword_score is None
    assert results[0].rrf == approx(2 / 61)
    assert results[1].rrf == approx(1 / 62)


def test_keyword_match_overtakes_vector_order(corpus):
    results = search(corpus, "harming other people", embed=recursion_like)
    assert [r.title for r in results] == ["harm.txt", "recursion.txt"]
    assert [r.vector_rank for r in results] == [2, 1]


def test_keyword_only_match_is_returned(corpus, monkeypatch):
    monkeypatch.setattr(rs, "CANDIDATES", 1)
    results = search(corpus, "harming other people", embed=recursion_like)
    harm = next(r for r in results if r.title == "harm.txt")
    assert harm.vector_rank is None and harm.vector_score is None
    assert harm.keyword_rank == 1 and "liberty" in harm.content


def test_stopword_only_query_falls_back_to_vector(corpus):
    results = search(corpus, "What is it?")
    assert len(results) == 2
    assert all(r.keyword_rank is None for r in results)
    assert [r.vector_rank for r in results] == [1, 2]


def test_punctuation_in_query_does_not_raise(corpus):
    results = search(corpus, '"harm" -(OR & |!')
    assert results[0].title == "harm.txt" and results[0].keyword_rank == 1


def test_course_filter_applies_to_keyword(corpus):
    results = search(corpus, "harm", course="CPSC")
    assert [r.title for r in results] == ["recursion.txt"]
    assert results[0].keyword_rank is None
