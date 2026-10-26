import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://courselens:courselens@localhost:5432/courselens"
)
MODE = os.environ.get("MODE", "public")  # 'public' | 'private'
EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-m3")  # Hugging Face model id
EMBED_DIM = 1024  # must match VECTOR(1024) in db/01-schema.sql
ANSWER_MODEL = os.environ.get("ANSWER_MODEL", "claude-sonnet-5-5")
