import re
from dataclasses import dataclass
from itertools import groupby

from ingest.parse import Paragraph
from ingest.slides import Slide

TARGET_TOKENS = 400


@dataclass
class Chunk:
    content: str
    location: str
    content_type: str
    token_count: int


def count_tokens(text: str) -> int:
    # ponytail: ~4 chars/token estimate; swap in the embedding model's tokenizer
    # if chunk sizes ever need to be exact.
    return len(text) // 4


def _split_long(p: Paragraph, target: int) -> list[Paragraph]:
    """Split a paragraph over `target` tokens on sentence boundaries."""
    if count_tokens(p.text) <= target:
        return [p]
    # ponytail: a single sentence longer than `target` stays whole (never split mid-sentence).
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", p.text.strip()):
        if current and count_tokens(f"{current} {sentence}") > target:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    pieces.append(current)
    return [Paragraph(text, p.section, p.index) for text in pieces]


def _join(paras: list[Paragraph]) -> str:
    return "\n\n".join(p.text for p in paras)


def _make(paras: list[Paragraph]) -> Chunk:
    first, last = paras[0].index, paras[-1].index
    span = f"¶ {first}" if first == last else f"¶ {first}–{last}"
    location = f"{paras[0].section}, {span}" if paras[0].section else span
    content = _join(paras)
    return Chunk(content, location, "prose", count_tokens(content))


def chunk_prose(paragraphs: list[Paragraph], target: int = TARGET_TOKENS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for _, section in groupby(paragraphs, key=lambda p: p.section):
        buf: list[Paragraph] = []
        for para in section:
            for piece in _split_long(para, target):
                if buf and count_tokens(_join(buf + [piece])) > target:
                    chunks.append(_make(buf))
                    overlap = buf[-1]
                    buf = [overlap] if count_tokens(_join([overlap, piece])) <= target else []
                buf.append(piece)
        if buf:
            chunks.append(_make(buf))
    return chunks


def chunk_slides(deck_title: str, slides: list[Slide]) -> list[Chunk]:
    """One chunk per slide; image-only slides (no title, no body) are dropped."""
    chunks = []
    for s in slides:
        if not (s.title.strip() or s.body.strip()):
            continue
        head = "\n".join(filter(None, [deck_title, s.title]))
        content = (head + "\n\n" + s.body).rstrip()
        chunks.append(Chunk(content, f"slide {s.number}", "slide", count_tokens(content)))
    return chunks
