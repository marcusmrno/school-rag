import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation
from pypdf import PdfReader


@dataclass
class Slide:
    number: int  # 1-based
    title: str  # "" if none
    body: str  # line breaks and relative indentation kept


def _norm(text: str) -> str:
    return " ".join(text.split())


def _key(line: str) -> str:
    # digits removed, so "6.100L Lecture 2   43" and "... 44" match
    return _norm(re.sub(r"\d", "", line))


def _lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def _boilerplate(pages: list[list[str]]) -> set[str]:
    """Line keys on more than half the pages (and at least 3): footers, running headers."""
    seen = Counter(k for lines in pages for k in {_key(line) for line in lines} if k)
    return {k for k, n in seen.items() if n > len(pages) / 2 and n >= 3}


def _body(lines: list[str], title: str, boiler: set[str]) -> str:
    lines = [line for line in lines if _key(line) not in boiler]
    for i, line in enumerate(lines):
        if _norm(line) == title:
            del lines[i]
            break
    common = min((len(line) - len(line.lstrip()) for line in lines), default=0)
    lines = [line[common:] for line in lines]
    # layout mode pads words apart; collapse that, but keep the leading indentation
    return "\n".join(re.match(r" *", line).group() + re.sub(r" {3,}", " ", line.lstrip()) for line in lines)


def parse_pdf_slides(path: Path) -> list[Slide]:
    # ponytail: two-column slides interleave line by line in layout mode; use per-column
    # cropping if such decks matter.
    pages = PdfReader(path).pages
    # plain mode follows content-stream order (title first); layout mode sorts by position
    plain = [_lines(p.extract_text() or "") for p in pages]
    layout = [_lines(p.extract_text(extraction_mode="layout")) for p in pages]
    boiler = _boilerplate(layout)
    slides = []
    for number, (first, lines) in enumerate(zip(plain, layout), 1):
        title = _norm(first[0]) if first else ""
        slides.append(Slide(number, title, _body(lines, title, boiler)))
    return slides


def _pptx_body(slide) -> str:
    lines = []
    for shape in slide.shapes:
        if shape.has_text_frame and shape != slide.shapes.title:
            for p in shape.text_frame.paragraphs:
                text = p.text.replace("\x0b", "\n")  # soft line break
                if text.strip():
                    lines.append("  " * p.level + text)
    return "\n".join(lines)


def parse_pptx_slides(path: Path) -> list[Slide]:
    # ponytail: tables, grouped shapes and speaker notes aren't read.
    slides = Presentation(path).slides
    return [
        Slide(n, s.shapes.title.text_frame.text.strip() if s.shapes.title else "", _pptx_body(s))
        for n, s in enumerate(slides, 1)
    ]
