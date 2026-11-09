from pathlib import Path

from ingest.slides import parse_pdf_slides, parse_pptx_slides

FIXTURE = Path(__file__).parent / "fixtures" / "ocw-lec02-sample.pdf"


def test_pdf_slide_numbers_and_titles():
    slides = parse_pdf_slides(FIXTURE)
    assert [s.number for s in slides] == [1, 2, 3, 4]
    assert [s.title for s in slides] == ["RECAP", "INPUT", "BRANCHING IN PYTHON", "BRANCHING IN PYTHON"]


def test_pdf_footer_is_dropped():
    for s in parse_pdf_slides(FIXTURE):
        assert "6.100L Lecture" not in s.title + s.body


def test_pdf_keeps_code_indentation():
    lines = parse_pdf_slides(FIXTURE)[2].body.splitlines()
    i = lines.index("if <condition>:")
    assert lines[i + 1].startswith(" ") and lines[i + 1].strip() == "<code>"
    assert "<rest of program>" in lines  # back at column 0


def test_pdf_repairs_split_words():
    body = parse_pdf_slides(FIXTURE)[2].body
    assert "has a value" in body and "valu e" not in body


def test_pptx_title_and_bullet_levels(pptx_deck):
    s = parse_pptx_slides(pptx_deck)[0]
    assert (s.number, s.title, s.body) == (1, "Loops", "First point\n  Sub point")


def test_pptx_keeps_code_indentation(pptx_deck):
    assert parse_pptx_slides(pptx_deck)[1].body == "for i in range(3):\n    print(i)"


def test_pptx_slide_without_title(pptx_deck):
    s = parse_pptx_slides(pptx_deck)[2]
    assert (s.title, s.body) == ("", "No title here")
