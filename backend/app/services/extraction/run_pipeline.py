"""CLI entry point to run commitment extraction and deduplication pipeline.

Usage:
    python -m app.services.extraction.run_pipeline
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.database import SessionLocal, create_tables
from app.services.extraction.commitment_pipeline import CommitmentPipeline


def main() -> None:
    print("Running Commitment Intelligence Pipeline...")
    create_tables()

    db = SessionLocal()
    try:
        pipeline = CommitmentPipeline(db=db)
        summary = pipeline.run()
        print("\n--- Commitment Pipeline Summary ---")
        print(json.dumps(summary, indent=2))
        print("-----------------------------------\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
