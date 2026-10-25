from __future__ import annotations

import sqlite3
from pathlib import Path

from app.analytics import Analytics
from app.ingestion import ingest_csv, rejected_rows


def test_ingestion_is_repeatable_and_tracks_rejections(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    csv_path.write_text(
        "Order Date,Product Name,Region,Sales,Returned\n"
        "2024-01-01,Desk,West,25.50,no\n"
        "not-a-date,Chair,East,10,no\n"
        "2024-01-03,,West,15,no\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "repeat.db"

    first = ingest_csv(csv_path, db_path)
    second = ingest_csv(csv_path, db_path)
    assert (first.loaded, first.updated, first.rejected) == (1, 0, 2)
    assert (second.loaded, second.updated, second.rejected) == (0, 1, 2)
    assert len(rejected_rows(db_path)) == 2
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1


def test_supplied_quantity_price_schema_derives_net_sales_and_status(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "challenge-format.csv"
    csv_path.write_text(
        "Transaction_Id,Order_date,Product,Region,Quantity,Unit_price,"
        "Discount_amount,Status\n"
        "A,03-01-2026,Stand,North,2,100,10,Completed\n"
        "B,04-01-2026,Mouse,South,1,50,0,Returned\n"
        "C,05-01-2026,Zero,West,0,500,0,Completed\n"
        "D,06-01-2026,Invalid,East,1,,0,Completed\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "challenge.db"

    summary = ingest_csv(csv_path, db_path)
    analytics = Analytics(db_path)

    assert (summary.loaded, summary.rejected) == (3, 1)
    assert analytics.total_revenue() == {"revenue": 190.0, "transaction_count": 2}
    assert analytics.monthly_revenue() == [
        {"month": "2026-01", "revenue": 190.0, "transaction_count": 2}
    ]
    assert len(rejected_rows(db_path)) == 1
