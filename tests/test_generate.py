from types import SimpleNamespace

from core import config
from generate.answer import REFUSE_BELOW, Answer, answer, validate_citations
from retrieval.search import ScoredChunk


def chunk(i, rerank=None):
    return ScoredChunk(i, "On Liberty", f"CHAPTER I, ¶ {i}", "PHIL", None, f"text {i}", i, 0.5, rerank=rerank)


class FakeClient:
    def __init__(self, text="", stop_reason="end_turn"):
        self.calls = []
        content = [SimpleNamespace(type="text", text=text)] if text else []
        response = SimpleNamespace(stop_reason=stop_reason, content=content)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: self.calls.append(kw) or response))


def test_keeps_valid_markers():
    text = "Harm limits power [1]. Speech is free [2]."
    assert validate_citations(text, 2) == (text, [1, 2])


def test_strips_out_of_range_markers():
    assert validate_citations("Harm [1]. Invented [4]. Zero [0].", 3) == ("Harm [1]. Invented. Zero.", [1])


def test_grouped_markers_split_and_filtered():
    assert validate_citations("Both agree [1, 5][2].", 3) == ("Both agree [1][2].", [1, 2])


def test_answer_with_valid_citation():
    result = answer("q", [chunk(1), chunk(2)], FakeClient("Power may only prevent harm [2]."))
    assert result == Answer("Power may only prevent harm [2].", True, [2])


def test_zero_valid_citations_becomes_not_found():
    assert answer("q", [chunk(1)], FakeClient("Mill was born in 1806 [7].")) == Answer("", False, [])


def test_not_found_sentinel():
    assert answer("q", [chunk(1)], FakeClient("NOT_FOUND")) == Answer("", False, [])


def test_refusal_is_not_found():
    assert answer("q", [chunk(1)], FakeClient(stop_reason="refusal")) == Answer("", False, [])


def test_no_chunks_skips_the_api():
    client = FakeClient("should not be used [1].")
    assert answer("q", [], client) == Answer("", False, [])
    assert client.calls == []


def test_request_numbers_sources_and_uses_config_model():
    client = FakeClient("x [1].")
    answer("What is harm?", [chunk(1), chunk(2)], client)
    call = client.calls[0]
    user = call["messages"][0]["content"]
    assert call["model"] == config.ANSWER_MODEL
    assert user.index('<source n="1"') < user.index('<source n="2"') < user.index("What is harm?")
    assert 'location="CHAPTER I, ¶ 2"' in user
    assert call["fallbacks"] == "default"


def test_weak_top_rerank_skips_claude():
    client = FakeClient("Power may only prevent harm [1].")
    assert answer("q", [chunk(1, rerank=REFUSE_BELOW / 2)], client) == Answer("", False, [])
    assert client.calls == []


def test_no_rerank_score_still_calls_claude():
    client = FakeClient("Power may only prevent harm [1].")
    assert answer("q", [chunk(1)], client).found
    assert len(client.calls) == 1
