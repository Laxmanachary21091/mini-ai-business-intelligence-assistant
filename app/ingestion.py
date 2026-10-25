"""CSV validation, cleaning, and idempotent loading into SQLite."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.db import connect_database, initialize_database


REQUIRED_COLUMNS = {"order_date", "product", "region"}
HEADER_ALIASES = {
    "order_date": {"order_date", "orderdate", "date", "transaction_date"},
    "product": {"product", "product_name", "item"},
    "region": {"region", "sales_region"},
    "sales": {"sales", "revenue", "amount", "sales_amount"},
    "returned": {"returned", "is_returned", "return"},
    "transaction_id": {"transaction_id", "transactionid", "order_id", "row_id"},
    "quantity": {"quantity", "qty"},
    "unit_price": {"unit_price", "unitprice", "price"},
    "discount_amount": {"discount_amount", "discount", "discountamount"},
    "status": {"status", "order_status"},
}
TRUE_VALUES = {"true", "yes", "y", "1", "returned"}
FALSE_VALUES = {"false", "no", "n", "0", "not returned"}
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d")


@dataclass(frozen=True)
class IngestionSummary:
    source_file: str
    loaded: int
    updated: int
    rejected: int


def _canonical_header(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
    for canonical, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return canonical
    return normalized


def _raw_hash(raw: dict[str, Any]) -> str:
    payload = json.dumps(raw, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_returned(value: str) -> int:
    normalized = value.strip().casefold()
    if not normalized:
        return 0
    if normalized in TRUE_VALUES:
        return 1
    if normalized in FALSE_VALUES:
        return 0
    raise ValueError("returned value must be a recognized true/false value")


def _parse_status(value: str) -> int:
    normalized = value.strip().casefold()
    if normalized == "returned":
        return 1
    if normalized in {
        "completed",
        "complete",
        "pending",
        "shipped",
        "processing",
        "cancelled",
        "canceled",
        "not returned",
    }:
        return 0
    raise ValueError("status is missing or not a recognized transaction status")


def _parse_date(value: str) -> datetime | None:
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), date_format)
        except ValueError:
            continue
    return None


def _record_key(
    transaction_id: str | None,
    order_date: str,
    product: str,
    region: str,
    sales: float,
    returned: int,
    occurrence: int,
) -> str:
    if transaction_id:
        return "id:" + transaction_id
    canonical = json.dumps(
        [order_date, product, region, format(sales, ".15g"), returned],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"row:{digest}:{occurrence}"


def ingest_csv(csv_path: Path, db_path: Path | None = None) -> IngestionSummary:
    """Validate and load one CSV; repeated loads do not duplicate transactions.

    Required input fields are date, product, and region plus either sales or
    quantity and unit price. Status/returned fields are optional and documented.
    """
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"Sales CSV does not exist: {csv_path}")
    try:
        frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise ValueError("Sales CSV is empty and has no header row") from exc

    original_columns = list(frame.columns)
    canonical_columns = [_canonical_header(str(column)) for column in original_columns]
    if len(set(canonical_columns)) != len(canonical_columns):
        raise ValueError("CSV contains multiple columns that map to the same field")
    missing = REQUIRED_COLUMNS.difference(canonical_columns)
    if "sales" not in canonical_columns and not {
        "quantity",
        "unit_price",
    }.issubset(canonical_columns):
        missing.add("sales or both quantity and unit_price")
    if missing:
        raise ValueError(
            "CSV is missing required columns: " + ", ".join(sorted(missing))
        )
    frame.columns = canonical_columns

    source_file = csv_path.name
    initialize_database(db_path)
    loaded = 0
    updated = 0
    rejected = 0
    duplicate_occurrences: dict[str, int] = {}

    with connect_database(db_path) as connection:
        for source_row, row in enumerate(frame.to_dict(orient="records"), start=2):
            raw = {str(key): str(value) for key, value in row.items()}
            reasons: list[str] = []
            raw_date = str(row.get("order_date", "")).strip()
            parsed_date = _parse_date(raw_date)
            if parsed_date is None:
                reasons.append("missing or invalid order_date")

            product = str(row.get("product", "")).strip()
            region = str(row.get("region", "")).strip()
            if not product:
                reasons.append("missing product")
            if not region:
                reasons.append("missing region")

            if "sales" in frame.columns:
                raw_sales = str(row.get("sales", "")).strip().replace(",", "")
                sales_value = pd.to_numeric(raw_sales, errors="coerce")
                sales = float(sales_value) if pd.notna(sales_value) else math.nan
            else:
                raw_quantity = str(row.get("quantity", "")).strip().replace(",", "")
                raw_unit_price = str(row.get("unit_price", "")).strip().replace(",", "")
                quantity_value = pd.to_numeric(raw_quantity, errors="coerce")
                unit_price_value = pd.to_numeric(raw_unit_price, errors="coerce")
                quantity = (
                    float(quantity_value) if pd.notna(quantity_value) else math.nan
                )
                unit_price = (
                    float(unit_price_value)
                    if pd.notna(unit_price_value)
                    else math.nan
                )
                discount_text = (
                    str(row.get("discount_amount", "")).strip().replace(",", "")
                )
                discount_value = (
                    pd.to_numeric(discount_text, errors="coerce")
                    if discount_text
                    else 0.0
                )
                discount = (
                    float(discount_value)
                    if pd.notna(discount_value)
                    else math.nan
                )
                if not math.isfinite(quantity) or quantity < 0:
                    reasons.append("quantity must be a finite, non-negative number")
                if not math.isfinite(unit_price) or unit_price < 0:
                    reasons.append("unit_price must be a finite, non-negative number")
                if not math.isfinite(discount) or discount < 0:
                    reasons.append(
                        "discount_amount must be a finite, non-negative number"
                    )
                sales = (
                    quantity * unit_price - discount
                    if all(
                        math.isfinite(value)
                        for value in (quantity, unit_price, discount)
                    )
                    else math.nan
                )
            if not math.isfinite(sales):
                reasons.append("missing or invalid sales")
            elif sales < 0:
                reasons.append("net sales cannot be negative")

            try:
                if "returned" in frame.columns:
                    returned = _parse_returned(str(row.get("returned", "")))
                elif "status" in frame.columns:
                    returned = _parse_status(str(row.get("status", "")))
                else:
                    returned = 0
            except ValueError as exc:
                reasons.append(str(exc))
                returned = 0

            if reasons:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO rejected_records
                        (source_file, source_row, raw_hash, raw_record, rejection_reason)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        source_file,
                        source_row,
                        _raw_hash(raw),
                        json.dumps(raw, ensure_ascii=False, sort_keys=True),
                        "; ".join(reasons),
                    ),
                )
                rejected += 1
                continue

            date_text = parsed_date.strftime("%Y-%m-%d")
            raw_id = str(row.get("transaction_id", "")).strip()
            transaction_id = raw_id or None
            content = [date_text, product, region, format(sales, ".15g"), returned]
            digest = hashlib.sha256(
                json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest()
            occurrence = duplicate_occurrences.get(digest, 0)
            duplicate_occurrences[digest] = occurrence + 1
            transaction_key = _record_key(
                transaction_id, date_text, product, region, sales, returned, occurrence
            )

            exists = connection.execute(
                "SELECT 1 FROM transactions WHERE transaction_key = ?",
                (transaction_key,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO transactions
                    (transaction_key, transaction_id, order_date, product, region,
                     sales, returned, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(transaction_key) DO UPDATE SET
                    transaction_id = excluded.transaction_id,
                    order_date = excluded.order_date,
                    product = excluded.product,
                    region = excluded.region,
                    sales = excluded.sales,
                    returned = excluded.returned,
                    source_file = excluded.source_file
                """,
                (
                    transaction_key,
                    transaction_id,
                    date_text,
                    product,
                    region,
                    sales,
                    returned,
                    source_file,
                ),
            )
            if exists:
                updated += 1
            else:
                loaded += 1

        connection.execute(
            """
            INSERT INTO ingestion_runs
                (source_file, loaded_count, updated_count, rejected_count)
            VALUES (?, ?, ?, ?)
            """,
            (source_file, loaded, updated, rejected),
        )

    return IngestionSummary(source_file, loaded, updated, rejected)


def rejected_record_count(db_path: Path | None = None) -> int:
    """Return the total number of distinct persisted rejected source rows."""
    initialize_database(db_path)
    with connect_database(db_path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM rejected_records").fetchone()[0])


def summary_as_dict(summary: IngestionSummary) -> dict[str, Any]:
    """Convert an ingestion result to a JSON-friendly mapping."""
    return asdict(summary)


def rejected_rows(db_path: Path | None = None) -> list[sqlite3.Row]:
    """Return rejected rows for inspection by scripts and tests."""
    initialize_database(db_path)
    with connect_database(db_path) as connection:
        return connection.execute(
            """
            SELECT source_file, source_row, raw_record, rejection_reason, rejected_at
            FROM rejected_records
            ORDER BY id
            """
        ).fetchall()
