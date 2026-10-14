import math

from core import config
from core.embeddings import embed_documents


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_vectors_have_schema_dimension_and_unit_length():
    vectors = embed_documents(["Liberty of thought.", "Utility and happiness."])
    assert len(vectors) == 2
    for v in vectors:
        assert len(v) == config.EMBED_DIM
        assert math.isclose(math.sqrt(dot(v, v)), 1.0, rel_tol=1e-3)


def test_similar_meaning_scores_higher_than_unrelated():
    question, relevant, unrelated = embed_documents([
        "When may society interfere with an individual?",
        "The only purpose for which power can be rightfully exercised over any member "
        "of a civilised community, against his will, is to prevent harm to others.",
        "Preheat the oven to 200 degrees and bake the bread for thirty minutes.",
    ])
    assert dot(question, relevant) > dot(question, unrelated)


def test_empty_input_returns_empty_list():
    assert embed_documents([]) == []
