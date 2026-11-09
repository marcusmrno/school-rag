import json
import logging
import os
from collections.abc import Callable
from pathlib import Path

import psycopg

from core import config
from core.db import to_vector
from ingest.chunk import chunk_prose, chunk_slides
from ingest.parse import parse_file
from ingest.slides import parse_pdf_slides, parse_pptx_slides

log = logging.getLogger(__name__)

SUPPORTED = {".txt", ".md", ".pdf", ".pptx"}
Embed = Callable[[list[str]], list[list[float]]]


def _load_sources(directory: Path) -> dict:
    path = directory / "sources.json"
    return json.loads(path.read_text()) if path.exists() else {}


def ingest_file(conn: psycopg.Connection, path: Path, course: str, meta: dict, embed: Embed) -> int:
    if config.MODE == "public" and not meta.get("license"):
        raise ValueError("public mode requires a license in sources.json")
    title = meta.get("title", path.stem)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        chunks = chunk_slides(title, parse_pdf_slides(path))
    elif suffix == ".pptx":
        chunks = chunk_slides(title, parse_pptx_slides(path))
    else:
        chunks = chunk_prose(parse_file(path))
    if not chunks:
        raise ValueError("no text found")
    vectors = embed([c.content for c in chunks])
    source_path = os.path.relpath(path)  # relative, so no local home-dir paths land in the DB

    with conn.transaction():
        conn.execute("DELETE FROM documents WHERE source_path = %s", (source_path,))
        doc_id = conn.execute(
            "INSERT INTO documents (course, title, source_path, source_url, license)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (course, title, source_path, meta.get("source_url"), meta.get("license")),
        ).fetchone()[0]
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (document_id, course, content_type, location, content, token_count, embedding)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s::vector)",
                [
                    (doc_id, course, c.content_type, c.location, c.content, c.token_count, to_vector(v))
                    for c, v in zip(chunks, vectors, strict=True)
                ],
            )
    return len(chunks)


def ingest_dir(
    conn: psycopg.Connection, directory: Path, course: str, embed: Embed
) -> tuple[int, list[tuple[str, str]]]:
    """Ingest every supported file; a failing file is logged and skipped, not fatal."""
    sources = _load_sources(directory)
    total, skipped = 0, []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in SUPPORTED:
            continue
        try:
            n = ingest_file(conn, path, course, sources.get(path.name, {}), embed)
        except Exception as e:  # model, parse and DB errors all mean "skip this file"
            log.warning("skipped %s: %s", path.name, e)
            skipped.append((path.name, str(e)))
            continue
        log.info("%s: %d chunks", path.name, n)
        total += n
    return total, skipped
