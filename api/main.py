import logging
import time
from typing import Annotated, Literal

import anthropic
import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints

from core.db import connect
from generate.answer import answer
from retrieval.search import search

log = logging.getLogger(__name__)

app = FastAPI(title="CourseLens")

NOT_FOUND = "I couldn't find this in the course material."
EXCERPT_CHARS = 300


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
        "citations": [
            {
                "n": n,
                "chunk_id": c.chunk_id,
                "title": c.title,
                "location": c.location,
                "course": c.course,
                "source_url": c.source_url,
                "excerpt": _excerpt(c.content),
            }
            for n in result.cited
            for c in [chunks[n - 1]]
        ],
        "debug": {
            "retrieved": [
                {"chunk_id": c.chunk_id, "vector_rank": c.vector_rank, "vector_score": c.vector_score}
                for c in chunks
            ],
            "timings_ms": {"search": round((t1 - t0) * 1000), "generate": round((t2 - t1) * 1000)},
        },
    }
