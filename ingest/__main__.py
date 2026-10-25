import argparse
import logging
import sys
from pathlib import Path

from core.db import connect
from core.embeddings import embed_documents
from ingest.pipeline import ingest_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a corpus directory into Postgres.")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--course", required=True, choices=["PHIL", "ENGL", "CPSC"])
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("ingest").setLevel(logging.INFO)

    with connect() as conn:
        total, skipped = ingest_dir(conn, args.directory, args.course, embed_documents)

    print(f"\n{total} chunks ingested, {len(skipped)} file(s) skipped")
    for name, error in skipped:
        print(f"  - {name}: {error}")
    sys.exit(1 if skipped else 0)


if __name__ == "__main__":
    main()
