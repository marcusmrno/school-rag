import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Paragraph:
    text: str
    section: str  # nearest heading above, "" if none
    index: int  # 1-based paragraph number within its section


_GUTENBERG_START = re.compile(r"^\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG.*$", re.M | re.I)
_GUTENBERG_END = re.compile(r"^\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG.*$", re.M | re.I)
_HEADING = re.compile(
    r"^(#{1,6}\s+.+"
    r"|(CHAPTER|Chapter|BOOK|Book|PART|Part|SECTION|Section|MEDITATION|Meditation)\s+[IVXLCDM\d]+\b.*)$"
)
_MAX_HEADING_CHARS = 120
# ponytail: contents entries are spotted by a right-aligned page number; dot
# leaders ("Introductory ....... 1") aren't matched, add them when a text needs it.
_CONTENTS_ENTRY = re.compile(r"\S\s{2,}\d+$")


def _strip_gutenberg(text: str) -> str:
    start = _GUTENBERG_START.search(text)
    end = _GUTENBERG_END.search(text)
    return text[start.end() if start else 0 : end.start() if end else len(text)]


def parse_text(text: str) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    section = ""
    counts: Counter[str] = Counter()  # per section, so front matter resumes after the contents
    for block in re.split(r"\n\s*\n", _strip_gutenberg(text)):
        joined = " ".join(block.split())
        if not joined:
            continue
        lines = block.strip().splitlines()
        # A contents-page entry: drop it, and since the heading above it was a
        # contents line too, fall back to front matter.
        if _CONTENTS_ENTRY.search(lines[-1].rstrip()):
            section = ""
            continue
        # ponytail: heading = short block whose first line looks like a heading; a
        # short paragraph like "Part II of the argument..." would be misread.
        if len(joined) <= _MAX_HEADING_CHARS and _HEADING.match(lines[0].strip()):
            section = joined.lstrip("# ").rstrip(".")
            continue
        counts[section] += 1
        paragraphs.append(Paragraph(joined, section, counts[section]))
    return paragraphs


def parse_file(path: Path) -> list[Paragraph]:
    if path.suffix.lower() not in {".txt", ".md"}:
        raise ValueError(f"unsupported file type: {path.suffix}")
    return parse_text(path.read_text(encoding="utf-8-sig"))
