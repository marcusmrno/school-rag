# CourseLens

Ask questions about course material and get answers cited to the exact page or slide.

## Local setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then set ANTHROPIC_API_KEY in .env
docker compose up -d --wait
python -m ingest corpus/public/phil --course PHIL   # first run downloads the embedding model (~2.3 GB)
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
