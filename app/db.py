"""SQLite database setup and connection helpers."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


DEFAULT_DATABASE_PATH = Path("data") / "sales.db"


def database_path() -> Path:
    """Return the configured SQLite path, defaulting to data/sales.db."""
    return Path(os.getenv("DATABASE_PATH", str(DEFAULT_DATABASE_PATH))).expanduser()


def connect_database(path: Path | None = None) -> sqlite3.Connection:
    """Open a regular database connection and return rows by column name."""
    db_path = path or database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(path: Path | None = None) -> None:
    """Create the transaction and ingestion audit tables if they do not exist."""
    with connect_database(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_key TEXT PRIMARY KEY,
                transaction_id TEXT,
                order_date TEXT NOT NULL,
                product TEXT NOT NULL,
                region TEXT NOT NULL,
                sales REAL NOT NULL CHECK (sales >= 0),
                returned INTEGER NOT NULL CHECK (returned IN (0, 1)),
                source_file TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_transactions_order_date
                ON transactions(order_date);
            CREATE INDEX IF NOT EXISTS idx_transactions_product
                ON transactions(product);
            CREATE INDEX IF NOT EXISTS idx_transactions_region
                ON transactions(region);

            CREATE TABLE IF NOT EXISTS rejected_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                source_row INTEGER NOT NULL,
                raw_hash TEXT NOT NULL,
                raw_record TEXT NOT NULL,
                rejection_reason TEXT NOT NULL,
                rejected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_file, source_row, raw_hash)
            );

            CREATE TABLE IF NOT EXISTS ingestion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                loaded_count INTEGER NOT NULL,
                updated_count INTEGER NOT NULL,
                rejected_count INTEGER NOT NULL,
                completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
