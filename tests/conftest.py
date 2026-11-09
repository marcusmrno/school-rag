import os
from pathlib import Path

import psycopg
import pytest
from pptx import Presentation
from pptx.util import Inches

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


@pytest.fixture
def pptx_deck(tmp_path):
    prs = Presentation()
    box = (Inches(1), Inches(4), Inches(6), Inches(2))

    s = prs.slides.add_slide(prs.slide_layouts[1])  # Title and Content
    s.shapes.title.text_frame.text = "Loops"
    body = s.placeholders[1].text_frame
    body.text = "First point"
    body.add_paragraph().text = "Sub point"
    body.paragraphs[1].level = 1

    s = prs.slides.add_slide(prs.slide_layouts[5])  # Title Only
    s.shapes.title.text_frame.text = "Code"
    s.shapes.add_textbox(*box).text_frame.text = "for i in range(3):\n    print(i)"

    s = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
    s.shapes.add_textbox(*box).text_frame.text = "No title here"

    path = tmp_path / "deck.pptx"
    prs.save(path)
    return path
