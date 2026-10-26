import pytest

from ingest.parse import Paragraph, parse_file, parse_text


def test_strips_gutenberg_header_and_footer():
    text = (
        "Header junk\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK ON LIBERTY ***\n\n"
        "Real text.\n\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK ON LIBERTY ***\n"
        "License junk"
    )
    assert [p.text for p in parse_text(text)] == ["Real text."]


def test_joins_hard_wrapped_lines():
    text = "The only freedom which deserves the name,\nis that of pursuing our own good."
    assert parse_text(text) == [
        Paragraph("The only freedom which deserves the name, is that of pursuing our own good.", "", 1)
    ]


def test_tracks_sections_and_resets_paragraph_index():
    text = (
        "Intro para.\n\n"
        "CHAPTER I.\nINTRODUCTORY.\n\n"
        "First para.\n\n"
        "Second para.\n\n"
        "CHAPTER II.\n\n"
        "Third para."
    )
    assert [(p.section, p.index, p.text) for p in parse_text(text)] == [
        ("", 1, "Intro para."),
        ("CHAPTER I. INTRODUCTORY", 1, "First para."),
        ("CHAPTER I. INTRODUCTORY", 2, "Second para."),
        ("CHAPTER II", 1, "Third para."),
    ]


def test_contents_page_entries_are_skipped():
    text = (
        "Preface.\n\n"
        "CONTENTS.\n\n"
        "CHAPTER I.\n                PAGE\nINTRODUCTORY      1\n\n"
        "CHAPTER II.\n\n"
        "OF THE LIBERTY OF THOUGHT\nAND DISCUSSION      28\n\n"
        "An epigraph.\n\n"
        "CHAPTER I.\n\n"
        "First para."
    )
    assert [(p.section, p.index, p.text) for p in parse_text(text)] == [
        ("", 1, "Preface."),
        ("", 2, "CONTENTS."),
        ("", 3, "An epigraph."),
        ("CHAPTER I", 1, "First para."),
    ]


def test_markdown_headings_are_sections():
    text = "# Week 3: Kant\n\nThe categorical imperative."
    assert parse_text(text) == [Paragraph("The categorical imperative.", "Week 3: Kant", 1)]


def test_ordinary_sentence_starting_with_part_is_not_a_heading():
    text = "Part of the argument is short."
    assert parse_text(text) == [Paragraph("Part of the argument is short.", "", 1)]


def test_parse_file_rejects_unsupported_types(tmp_path):
    path = tmp_path / "slides.pdf"
    path.write_bytes(b"%PDF")
    with pytest.raises(ValueError, match="unsupported file type"):
        parse_file(path)


def test_parse_file_reads_utf8_with_bom(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("﻿Hello.", encoding="utf-8")
    assert parse_file(path) == [Paragraph("Hello.", "", 1)]
