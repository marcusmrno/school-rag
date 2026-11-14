import re
from dataclasses import dataclass
from functools import cache

import anthropic

from core import config
from retrieval.search import ScoredChunk

SYSTEM_PROMPT = """You answer questions about course material using only the numbered sources provided.

- Use only what the sources say. Do not add outside knowledge, even if you know the answer.
- End every sentence that states a fact with the number of the source it comes from, like [1], or several, like [1][3].
- Cite only numbers that appear in the sources.
- If the sources do not contain the answer, reply with exactly NOT_FOUND and nothing else.
- Answer in plain prose, at most two short paragraphs, with no headings or lists."""

# Set from the eval data: the lowest top rerank score among answerable questions (0.0056), halved
# and rounded down. Below it the best passage is too weak to be worth a Claude call.
REFUSE_BELOW = 0.002

MARKER = re.compile(r"(\s*)\[(\d+(?:\s*,\s*\d+)*)\]")


@dataclass(frozen=True)
class Answer:
    text: str
    found: bool
    cited: list[int]


@cache
def default_client() -> anthropic.Anthropic:
    # max_retries=0 keeps the worst case at 30 s; the SDK's default 2 retries could make it 90 s.
    return anthropic.Anthropic(timeout=30.0, max_retries=0)


def validate_citations(text: str, n_chunks: int) -> tuple[str, list[int]]:
    kept: set[int] = set()

    def fix(m: re.Match) -> str:
        valid = [n for n in map(int, re.findall(r"\d+", m[2])) if 1 <= n <= n_chunks]
        kept.update(valid)
        return m[1] + "".join(f"[{n}]" for n in valid) if valid else ""

    return MARKER.sub(fix, text), sorted(kept)


def answer(question: str, chunks: list[ScoredChunk], client=None) -> Answer:
    not_found = Answer("", False, [])
    if not chunks or (chunks[0].rerank is not None and chunks[0].rerank < REFUSE_BELOW):
        return not_found
    sources = "\n".join(
        f'<source n="{i}" title="{c.title}" location="{c.location}">\n{c.content}\n</source>'
        for i, c in enumerate(chunks, 1)
    )
    user = f"<sources>\n{sources}\n</sources>\n\nQuestion: {question}"
    response = (client or default_client()).beta.messages.create(
        model=config.ANSWER_MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
        # ponytail: low effort for the 6 s latency target; tune once retrieval evals exist.
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return not_found
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    text, cited = validate_citations(text, len(chunks))
    return Answer(text, True, cited) if cited else not_found
