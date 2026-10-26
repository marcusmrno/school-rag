from dataclasses import dataclass

import psycopg

from core.db import to_vector
from core.embeddings import embed_documents
from ingest.pipeline import Embed


@dataclass(frozen=True)
class ScoredChunk:
    chunk_id: int
    title: str
    location: str
    course: str
    source_url: str | None
    content: str
    vector_rank: int  # 1-based
    vector_score: float  # cosine similarity


SQL = """
SELECT c.id, d.title, c.location, c.course, d.source_url, c.content,
       1 - (c.embedding <=> %(q)s::vector) AS score
FROM chunks c JOIN documents d ON d.id = c.document_id
WHERE %(course)s::text IS NULL OR c.course = %(course)s
ORDER BY c.embedding <=> %(q)s::vector
LIMIT %(k)s
"""


def search(
    conn: psycopg.Connection,
    query: str,
    course: str | None = None,
    k: int = 5,
    embed: Embed = embed_documents,
) -> list[ScoredChunk]:
    # ponytail: HNSW applies the WHERE after finding its candidates (40 by default), so a small
    # course could get fewer than k rows; iterative scan keeps searching until k rows match.
    conn.execute("SET hnsw.iterative_scan = strict_order")
    q = to_vector(embed([query])[0])
    rows = conn.execute(SQL, {"q": q, "course": course, "k": k}).fetchall()
    return [ScoredChunk(*row[:6], vector_rank=i, vector_score=row[6]) for i, row in enumerate(rows, 1)]
