import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated, Literal

import anthropic
import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints

from core.db import connect
from core.embeddings import model as embed_model
from generate.answer import answer
from retrieval.rerank import model as rerank_model
from retrieval.search import search

log = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load both models before serving, so a failed load stops startup instead of the first question.
    embed_model()
    rerank_model()
    yield


app = FastAPI(title="CourseLens", lifespan=lifespan)

NOT_FOUND = "I couldn't find this in the course material."
EXCERPT_CHARS = 300
NEAREST = 3


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    course: Literal["PHIL", "ENGL", "CPSC"] | None = None


@app.get("/health")
def health():
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
    except psycopg.OperationalError:
        return JSONResponse({"status": "db unreachable"}, status_code=503)
    return {"status": "ok"}


def _excerpt(content: str) -> str:
    return content[:EXCERPT_CHARS] + ("…" if len(content) > EXCERPT_CHARS else "")


def _source(n: int, c) -> dict:
    return {
        "n": n,
        "chunk_id": c.chunk_id,
        "title": c.title,
        "location": c.location,
        "course": c.course,
        "source_url": c.source_url,
        "excerpt": _excerpt(c.content),
    }


@app.post("/ask")
def ask(req: AskRequest):
    try:
        t0 = time.perf_counter()
        with connect() as conn:
            chunks = search(conn, req.question, req.course)
        t1 = time.perf_counter()
        result = answer(req.question, chunks)
        t2 = time.perf_counter()
    except psycopg.OperationalError:
        return JSONResponse({"detail": "database unreachable"}, status_code=503)
    except anthropic.APIError:
        log.exception("claude call failed")
        return JSONResponse(
            {"detail": "The answer service is unavailable, try again in a minute."}, status_code=503
        )

    return {
        "answer": result.text if result.found else NOT_FOUND,
        "found": result.found,
        "citations": [_source(n, chunks[n - 1]) for n in result.cited],
        "nearest": [] if result.found else [_source(n, c) for n, c in enumerate(chunks[:NEAREST], 1)],
        "debug": {
            "retrieved": [
                {
                    "chunk_id": c.chunk_id,
                    "title": c.title,
                    "location": c.location,
                    "vector_rank": c.vector_rank,
                    "vector_score": c.vector_score,
                    "keyword_rank": c.keyword_rank,
                    "keyword_score": c.keyword_score,
                    "rrf": c.rrf,
                    "rerank": c.rerank,
                }
                for c in chunks
            ],
            "rerank_skipped": bool(chunks) and chunks[0].rerank is None,
            "timings_ms": {"search": round((t1 - t0) * 1000), "generate": round((t2 - t1) * 1000)},
        },
    }
