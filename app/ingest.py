"""Command-line entry point for loading a sales CSV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db import database_path
from app.ingestion import ingest_csv, summary_as_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a sales CSV into SQLite.")
    parser.add_argument("csv_path", type=Path, help="Path to the source sales CSV")
    parser.add_argument(
        "--database",
        type=Path,
        default=database_path(),
        help="SQLite database path (default: DATABASE_PATH or data/sales.db)",
    )
    args = parser.parse_args()
    summary = ingest_csv(args.csv_path, args.database)
    print(json.dumps(summary_as_dict(summary), indent=2))


if __name__ == "__main__":
    main()
