CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  id          SERIAL PRIMARY KEY,
  course      TEXT NOT NULL,            -- 'PHIL' | 'ENGL' | 'CPSC'
  title       TEXT NOT NULL,
  source_path TEXT NOT NULL UNIQUE,
  source_url  TEXT,                     -- link shown in UI (public)
  license     TEXT,                     -- required in public mode
  ingested_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chunks (
  id           SERIAL PRIMARY KEY,
  document_id  INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  course       TEXT NOT NULL,           -- denormalized for filtering
  content_type TEXT NOT NULL,           -- 'prose' | 'slide'
  location     TEXT NOT NULL,           -- 'CHAPTER II, ¶ 3–5' | 'slide 12'
  content      TEXT NOT NULL,
  token_count  INT NOT NULL,
  embedding    VECTOR(1024) NOT NULL,   -- must equal EMBED_DIM (bge-m3 outputs 1024)
  tsv          TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks USING gin (tsv);
CREATE INDEX ON chunks (course);

CREATE TABLE IF NOT EXISTS spend (day DATE PRIMARY KEY, usd NUMERIC NOT NULL DEFAULT 0);
