# CourseLens

Ask questions about course material and get answers cited to the exact page or slide.

## Local setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d --wait
python -m ingest corpus/public/phil --course PHIL   # first run downloads the embedding model (~2.3 GB)
uvicorn api.main:app --reload
```

Run tests with `python -m pytest` (integration tests skip unless the Docker DB is up).
