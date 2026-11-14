import math
import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://courselens:courselens@localhost:5432/courselens"
)
MODE = os.environ.get("MODE", "public")  # 'public' | 'private'
EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-m3")  # Hugging Face model id
RERANK_MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")  # Hugging Face model id
EMBED_DIM = 1024  # must match VECTOR(1024) in db/01-schema.sql
ANSWER_MODEL = os.environ.get("ANSWER_MODEL", "claude-sonnet-5-5")
DAILY_BUDGET_USD = float(os.environ.get("DAILY_BUDGET_USD", "0.30"))
assert math.isfinite(DAILY_BUDGET_USD), "DAILY_BUDGET_USD must be a finite number"
RERANK_CANDIDATES = int(os.environ.get("RERANK_CANDIDATES", "20"))  # fused results rescored by the reranker
