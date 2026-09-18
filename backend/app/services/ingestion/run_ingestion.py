"""CLI entry point to run Data Pack ingestion.

Usage:
    python -m app.services.ingestion.run_ingestion
    or
    python -m app.services.ingestion.run_ingestion --path /path/to/executive_data_pack.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add backend directory to sys.path if not present
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import settings
from app.core.database import SessionLocal, create_tables
from app.services.ingestion.ingestion_service import IngestionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest executive data pack into database.")
    parser.add_argument(
        "--path",
        default=settings.data_pack_path,
        help="Path to the executive data pack markdown file.",
    )
    args = parser.parse_args()

    print(f"Ingesting Data Pack from: {args.path}")
    create_tables()

    db = SessionLocal()
    try:
        service = IngestionService(db=db, data_pack_path=args.path)
        summary = service.run()
        print("\n--- Ingestion Summary ---")
        print(json.dumps(summary, indent=2))
        print("-------------------------\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
