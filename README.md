# CourseLens

Ask questions about course material and get answers cited to the exact page or slide.

## Local setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then set ANTHROPIC_API_KEY in .env
docker compose up -d --wait
python -m ingest corpus/public/phil --course PHIL   # first run downloads the embedding model (~2.3 GB); the first question also downloads the reranker (~2.3 GB)
python -m ingest corpus/public/engl --course ENGL
python -m ingest corpus/public/cpsc --course CPSC
```

The full corpus takes about 10 minutes to embed. Licenses are listed in `corpus/public/SOURCES.md`.

```bash
uvicorn api.main:app --reload
```

With the API running, start the web page and open http://localhost:3000:

```bash
cd web && npm install && npm run dev
```

Run tests with `python -m pytest` (integration tests skip unless the Docker DB is up).

## Evaluation

48 hand-written questions (40 answerable with gold passages, 8 the corpus cannot answer) in `evals/questions.jsonl`.

```bash
python -m evals.run             # retrieval only, no API calls
python -m evals.run --answers   # also generates answers (calls Claude, ~150 requests)
```

- **Hit@5**: share of answerable questions whose gold passage is in the top 5.
- **MRR**: mean reciprocal rank of the first gold passage, over the top 5 (MRR@5).
- **Search p50**: median in-process search time.
- **Citation**: share of answerable questions whose answer cites a gold passage; a wrongly refused question counts as wrong.
- **Refusal**: share of unanswerable questions that got a not-found answer.
- **Answer p50 / p95**: search plus Claude time, in seconds.

| Config | Hit@5 | MRR | Search p50 (ms) | Citation | Refusal | Answer p50 (s) | Answer p95 (s) |
|---|---|---|---|---|---|---|---|
| vector | 0.68 | 0.50 | 146 | 0.68 | 1.00 | 2.1 | 3.6 |
| hybrid | 0.70 | 0.51 | 150 | 0.70 | 1.00 | 2.3 | 3.7 |
| hybrid_rerank | 0.85 | 0.62 | 2131 | 0.85 | 1.00 | 4.4 | 5.7 |

Adding keyword search to vector search helped only a little here (Hit@5 0.68 to 0.70). The cross-encoder reranker is what moved the numbers: Hit@5 0.85 and MRR 0.62, at the cost of about 2 s of search on an M2 (MPS, float16, 256-token passages, 20 candidates). Passage length and candidate count trade quality for speed (from a separate retrieval-only sweep): 512 tokens in float32 reached Hit@5 0.80 but took about 10.9 s, and 10 candidates took about 1.5 s at Hit@5 0.75. Citation matches Hit@5 question for question in every config, so answer quality is limited by retrieval, not by Claude. All three configs refused every unanswerable question; with reranking, the score threshold in `generate/answer.py` catches 3 of them before Claude is called, without refusing any answerable question.
