"""Score retrieval (and optionally answers) against gold passages: python -m evals.run [--answers]."""

import argparse
import json
import statistics
import time
from datetime import date
from pathlib import Path

import anthropic
import psycopg

from core.db import connect
from generate.answer import answer
from retrieval.search import search

CONFIGS: dict[str, dict] = {
    "vector": {"keyword": False, "rerank": None},
    "hybrid": {"rerank": None},
    "hybrid_rerank": {},
}
QUESTIONS = Path(__file__).parent / "questions.jsonl"
RESULTS = Path(__file__).parent / "results"
MAX_MATCHES = 3  # a quote matching more chunks than this is too generic to be gold

GOLD_SQL = """
SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id
WHERE d.title = %s AND strpos(regexp_replace(lower(c.content), '[\\s\\u00a0]+', ' ', 'g'), %s) > 0
"""


def load_questions(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def resolve_gold(conn: psycopg.Connection, gold: list[dict]) -> set[int]:
    ids: set[int] = set()
    for g in gold:
        found = [r[0] for r in conn.execute(GOLD_SQL, (g["title"], normalize(g["quote"])))]
        if not 1 <= len(found) <= MAX_MATCHES:
            raise ValueError(
                f"gold quote matches {len(found)} chunks (want 1-{MAX_MATCHES}) "
                f"in {g['title']!r}: {g['quote']!r}"
            )
        ids.update(found)
    return ids


def first_gold_rank(ids: list[int], gold: set[int]) -> int | None:
    return next((i for i, id_ in enumerate(ids, 1) if id_ in gold), None)


def run_config(conn, name, questions, gold_ids, answers):
    search(conn, "warm up", **CONFIGS[name])  # untimed: loads the models
    # ponytail: retries so one API hiccup doesn't discard a whole paid run; a retried call
    # inflates that question's latency.
    client = anthropic.Anthropic(timeout=60.0, max_retries=3) if answers else None
    records = []
    for q in questions:
        gold = gold_ids[q["id"]]
        t0 = time.perf_counter()
        chunks = search(conn, q["question"], **CONFIGS[name])
        search_ms = (time.perf_counter() - t0) * 1000
        rec = {
            "id": q["id"],
            "course": q["course"],
            "answerable": bool(q["gold"]),
            "rank": first_gold_rank([c.chunk_id for c in chunks], gold),
            "top_rerank": chunks[0].rerank if chunks else None,
            "search_ms": search_ms,
        }
        if answers:
            t1 = time.perf_counter()
            result = answer(q["question"], chunks, client=client)
            rec["total_ms"] = search_ms + (time.perf_counter() - t1) * 1000
            rec["found"] = result.found
            rec["cited_gold"] = any(chunks[n - 1].chunk_id in gold for n in result.cited)
        records.append(rec)
    return records


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(records: list[dict]) -> dict:
    yes = [r for r in records if r["answerable"]]
    no = [r for r in records if not r["answerable"]]
    out = {
        "hit_at_5": mean([r["rank"] is not None and r["rank"] <= 5 for r in yes]),
        "mrr": mean([1 / r["rank"] if r["rank"] else 0 for r in yes]),
        "search_p50_ms": statistics.median(r["search_ms"] for r in records),
        "citation": None, "refusal": None, "answer_p50_s": None, "answer_p95_s": None,
    }
    if records and "found" in records[0]:
        secs = [r["total_ms"] / 1000 for r in records]
        out["citation"] = mean([r["found"] and r["cited_gold"] for r in yes])
        out["refusal"] = mean([not r["found"] for r in no])
        out["answer_p50_s"] = statistics.median(secs)
        out["answer_p95_s"] = statistics.quantiles(secs, n=20)[18] if len(secs) > 1 else secs[0]
    return out


def cell(value, fmt):
    return "–" if value is None else format(value, fmt)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", nargs="+", choices=list(CONFIGS), default=list(CONFIGS))
    parser.add_argument("--answers", action="store_true", help="also generate answers (calls Claude)")
    args = parser.parse_args()

    questions = load_questions(QUESTIONS)
    with connect() as conn:
        gold_ids = {q["id"]: resolve_gold(conn, q["gold"]) for q in questions}
        RESULTS.mkdir(parents=True, exist_ok=True)
        rows = ["| Config | Hit@5 | MRR | Search p50 (ms) | Citation | Refusal | Answer p50 (s) | Answer p95 (s) |",
                "|---|---|---|---|---|---|---|---|"]
        for name in args.config:
            records = run_config(conn, name, questions, gold_ids, args.answers)
            s = summarize(records)
            path = RESULTS / f"{date.today().isoformat()}-{name}.json"
            path.write_text(json.dumps({"config": name, "summary": s, "records": records}, indent=2))
            rows.append(
                f"| {name} | {cell(s['hit_at_5'], '.2f')} | {cell(s['mrr'], '.2f')} "
                f"| {cell(s['search_p50_ms'], '.0f')} | {cell(s['citation'], '.2f')} "
                f"| {cell(s['refusal'], '.2f')} | {cell(s['answer_p50_s'], '.1f')} "
                f"| {cell(s['answer_p95_s'], '.1f')} |"
            )
    print("\n".join(rows))


if __name__ == "__main__":
    main()
