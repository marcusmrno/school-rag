from retrieval.rerank import rerank_scores

HARM_SENTENCE = (
    "The only purpose for which power can be rightfully exercised over any member "
    "of a civilised community, against his will, is to prevent harm to others."
)
BREAD_SENTENCE = "Preheat the oven to 200 degrees and bake the bread for thirty minutes."


def test_relevant_passage_scores_higher():
    relevant, unrelated = rerank_scores(
        "When may society interfere with an individual?", [HARM_SENTENCE, BREAD_SENTENCE]
    )
    assert 0 <= unrelated < relevant <= 1


def test_empty_passages():
    assert rerank_scores("q", []) == []
