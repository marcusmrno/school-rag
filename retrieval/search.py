import logging
from collections.abc import Callable
from dataclasses import dataclass, replace

import psycopg

from core import config
from core.db import to_vector
from core.embeddings import embed_documents
from ingest.pipeline import Embed
from retrieval.rerank import rerank_scores

log = logging.getLogger(__name__)

Rerank = Callable[[str, list[str]], list[float]]


@dataclass(frozen=True)
class ScoredChunk:
    chunk_id: int
    title: str
    location: str
    course: str
    source_url: str | None
    content: str
    vector_rank: int | None = None  # 1-based
    vector_score: float | None = None  # cosine similarity
    keyword_rank: int | None = None  # 1-based
    keyword_score: float | None = None  # ts_rank_cd
    rrf: float = 0.0  # fused score
    rerank: float | None = None  # cross-encoder score, 0-1


CANDIDATES = 20  # per-list candidates fed into the fusion
RRF_K = 60

VECTOR_SQL = """
SELECT c.id, d.title, c.location, c.course, d.source_url, c.content,
       1 - (c.embedding <=> %(q)s::vector) AS score
FROM chunks c JOIN documents d ON d.id = c.document_id
WHERE %(course)s::text IS NULL OR c.course = %(course)s
ORDER BY c.embedding <=> %(q)s::vector
LIMIT %(n)s
"""

# ponytail: plainto_tsquery ANDs the terms, so long questions often match nothing; fusion then
# falls back to vector order. Upgrade path: rewrite the question into key terms first.
KEYWORD_SQL = """
SELECT c.id, d.title, c.location, c.course, d.source_url, c.content,
       ts_rank_cd(c.tsv, q) AS score
FROM chunks c JOIN documents d ON d.id = c.document_id,
     plainto_tsquery('english', %(query)s) q
WHERE c.tsv @@ q AND (%(course)s::text IS NULL OR c.course = %(course)s)
ORDER BY score DESC, c.id
LIMIT %(n)s
"""


def rrf(rankings: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    """Reciprocal rank fusion: id -> sum of 1 / (k + rank), highest first, ties in first-seen order."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, id_ in enumerate(ranking, 1):
            scores[id_] = scores.get(id_, 0.0) + 1 / (k + rank)
    return {id_: scores[id_] for id_ in sorted(scores, key=scores.get, reverse=True)}


def search(
    conn: psycopg.Connection,
    query: str,
    course: str | None = None,
    k: int = 5,
    embed: Embed = embed_documents,
    keyword: bool = True,
    rerank: Rerank | None = rerank_scores,
) -> list[ScoredChunk]:
    # ponytail: HNSW applies the WHERE after finding its candidates (40 by default), so a small
    # course could get fewer than k rows; iterative scan keeps searching until k rows match.
    conn.execute("SET hnsw.iterative_scan = strict_order")
    q = to_vector(embed([query])[0])
    params = {"course": course, "n": CANDIDATES}
    vector = conn.execute(VECTOR_SQL, {**params, "q": q}).fetchall()
    kw = conn.execute(KEYWORD_SQL, {**params, "query": query}).fetchall() if keyword else []
    rows = {r[0]: r for r in kw + vector}
    vrank = {r[0]: (i, r[6]) for i, r in enumerate(vector, 1)}
    krank = {r[0]: (i, r[6]) for i, r in enumerate(kw, 1)}
    fused = rrf([[r[0] for r in vector], [r[0] for r in kw]])
    chunks = [
        ScoredChunk(
            *rows[id_][:6],
            *vrank.get(id_, (None, None)),
            *krank.get(id_, (None, None)),
            rrf=score,
        )
        for id_, score in list(fused.items())[:config.RERANK_CANDIDATES if rerank else k]
    ]
    if rerank and chunks:
        try:
            scores = rerank(query, [c.content for c in chunks])
            # stable sort: ties keep fused order
            chunks = sorted(
                (replace(c, rerank=s) for c, s in zip(chunks, scores, strict=True)),
                key=lambda c: c.rerank,
                reverse=True,
            )
        # ponytail: broad except hides any reranker error behind fused order; the log is where to look.
        except Exception:
            log.exception("rerank failed, using fused order")
    return chunks[:k]
