import pytest

from core.embeddings import embed_documents
from ingest.pipeline import ingest_file
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
