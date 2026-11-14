FROM python:3.12-slim AS deps
ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
# CPU-only torch first, so sentence-transformers doesn't pull the CUDA build
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

FROM deps AS app
ENV HF_HOME=/models
RUN useradd --uid 1000 --create-home app \
    && mkdir /models && chown app:app /models /srv
USER app
COPY --chown=app:app api/ api/
COPY --chown=app:app core/ core/
COPY --chown=app:app generate/ generate/
# retrieval.search imports a type from ingest
COPY --chown=app:app ingest/ ingest/
COPY --chown=app:app retrieval/ retrieval/
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}

FROM app AS final
# bake both models into the image so cold starts don't download them
RUN python -c "from core.embeddings import model as e; from retrieval.rerank import model as r; e(); r()"
# models are baked in; skip the Hub revision check on every cold start
ENV HF_HUB_OFFLINE=1
