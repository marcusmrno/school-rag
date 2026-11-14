import logging
import threading
import time
from contextlib import asynccontextmanager, nullcontext
from typing import Annotated, Literal

import anthropic
import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints

from api.limits import RateLimiter, add_spend, client_ip, spent_today
from core import config
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

limiter = RateLimiter([(10, 600), (50, 86_400)])

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


BUDGET_USED = "demo budget used up for today, try tomorrow"
# ponytail: one Claude call at a time, re-checking the budget inside the lock, so a burst of
# requests can't all pass the check before any spend is recorded. Serialises answers on the single
# instance; reserving an estimated cost in the database first is the upgrade for more instances.
_paid = threading.Lock()

@app.post("/ask")
def ask(req: AskRequest, request: Request):
    public = config.MODE != "private"  # a typo in MODE keeps the limits on
    if public and not limiter.allow(client_ip(request)):
        return JSONResponse({"detail": "Too many questions. Try again in a few minutes."}, status_code=429)
    try:
        with connect() as conn:
            if public and spent_today(conn) >= config.DAILY_BUDGET_USD:
                return JSONResponse({"detail": BUDGET_USED}, status_code=503)
            t0 = time.perf_counter()
            chunks = search(conn, req.question, req.course)
            t1 = time.perf_counter()
            with _paid if public else nullcontext():
                if public and spent_today(conn) >= config.DAILY_BUDGET_USD:
                    return JSONResponse({"detail": BUDGET_USED}, status_code=503)
                result = answer(req.question, chunks)
                if public and result.cost_usd > 0:
                    add_spend(conn, result.cost_usd)
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
