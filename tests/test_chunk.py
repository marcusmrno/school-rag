from ingest.chunk import chunk_prose, chunk_slides, count_tokens
from ingest.parse import Paragraph
from ingest.slides import Slide

WORDS = ("word " * 8).strip()  # 39 chars ≈ 9 tokens


def para(index, section="", text=WORDS):
    return Paragraph(text, section, index)


def test_small_paragraphs_merge_into_one_chunk():
    chunks = chunk_prose([para(1), para(2), para(3)], target=400)
    assert len(chunks) == 1
    assert chunks[0].location == "¶ 1–3"
    assert chunks[0].content == "\n\n".join([WORDS] * 3)
    assert chunks[0].content_type == "prose"
    assert chunks[0].token_count == count_tokens(chunks[0].content)


def test_chunks_overlap_by_one_paragraph():
    chunks = chunk_prose([para(i) for i in range(1, 5)], target=25)
    assert [c.location for c in chunks] == ["¶ 1–2", "¶ 2–3", "¶ 3–4"]


def test_does_not_cross_section_boundaries():
    chunks = chunk_prose([para(1, "A"), para(1, "B")], target=400)
    assert [c.location for c in chunks] == ["A, ¶ 1", "B, ¶ 1"]


def test_long_paragraph_splits_on_sentences():
    text = ("One two three four five six seven. " * 10).strip()
    chunks = chunk_prose([para(1, text=text)], target=20)
    assert len(chunks) > 1
    assert all(c.content.endswith(".") for c in chunks)
    assert all(c.token_count <= 20 for c in chunks)
    assert all(c.location == "¶ 1" for c in chunks)


def test_empty_input_gives_no_chunks():
    assert chunk_prose([]) == []


def test_slide_chunk_prepends_deck_and_slide_title():
    [c] = chunk_slides("Lecture 2", [Slide(3, "Loops", "for i in x:\n    print(i)")])
    assert c.content == "Lecture 2\nLoops\n\nfor i in x:\n    print(i)"
    assert (c.location, c.content_type) == ("slide 3", "slide")
    assert c.token_count == count_tokens(c.content)


def test_slide_without_text_gives_no_chunk():
    chunks = chunk_slides("Deck", [Slide(1, "", ""), Slide(2, "Title only", "")])
    assert [c.location for c in chunks] == ["slide 2"]
