import os
from pathlib import Path

import psycopg
import pytest

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://courselens:courselens@localhost:5432/courselens_test"
)
SCHEMA = Path(__file__).parent.parent / "db" / "01-schema.sql"


@pytest.fixture
def conn():
    try:
        conn = psycopg.connect(TEST_DB, autocommit=True)
    except psycopg.OperationalError:
        pytest.skip("test DB not reachable; run `docker compose up -d --wait`")
    conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    conn.execute(SCHEMA.read_text())
    yield conn
    conn.close()
