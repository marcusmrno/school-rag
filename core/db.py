import psycopg

from core import config


def connect(url: str | None = None) -> psycopg.Connection:
    """Autocommit connection; wrap multi-statement writes in conn.transaction()."""
    return psycopg.connect(url or config.DATABASE_URL, autocommit=True)


def to_vector(values: list[float]) -> str:
    """Format floats as a pgvector literal. Use in SQL as %s::vector."""
    return "[" + ",".join(map(str, values)) + "]"
