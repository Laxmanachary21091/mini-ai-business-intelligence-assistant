"""Fixed, read-only SQLite analytics queries."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db import database_path, initialize_database


REVENUE_POLICY = (
    "Revenue is the sum of the non-negative sales amount for transactions whose "
    "returned flag is false. Returned transactions are excluded, not subtracted."
)


class Analytics:
    """Execute only predefined SQL aggregations against the transactions table."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or database_path()
        initialize_database(self.db_path)

    def _query(self, sql: str, parameters: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        uri = f"{self.db_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            return connection.execute(sql, parameters).fetchall()

    def total_revenue(self) -> dict[str, int | float]:
        row = self._query(
            """
            SELECT COALESCE(SUM(sales), 0) AS revenue,
                   COUNT(*) AS transaction_count
            FROM transactions
            WHERE returned = 0
            """
        )[0]
        return {
            "revenue": float(row["revenue"]),
            "transaction_count": int(row["transaction_count"]),
        }

    def top_product(self) -> dict[str, int | float | str] | None:
        rows = self._query(
            """
            SELECT product, SUM(sales) AS revenue, COUNT(*) AS transaction_count
            FROM transactions
            WHERE returned = 0
            GROUP BY product
            ORDER BY revenue DESC, product ASC
            LIMIT 1
            """
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "product": str(row["product"]),
            "revenue": float(row["revenue"]),
            "transaction_count": int(row["transaction_count"]),
        }

    def monthly_revenue(self) -> list[dict[str, int | float | str]]:
        rows = self._query(
            """
            SELECT strftime('%Y-%m', order_date) AS month,
                   SUM(sales) AS revenue,
                   COUNT(*) AS transaction_count
            FROM transactions
            WHERE returned = 0
            GROUP BY strftime('%Y-%m', order_date)
            ORDER BY month ASC
            """
        )
        return [
            {
                "month": str(row["month"]),
                "revenue": float(row["revenue"]),
                "transaction_count": int(row["transaction_count"]),
            }
            for row in rows
        ]

    def top_region(self) -> dict[str, int | float | str] | None:
        rows = self._query(
            """
            SELECT region, SUM(sales) AS revenue, COUNT(*) AS transaction_count
            FROM transactions
            WHERE returned = 0
            GROUP BY region
            ORDER BY revenue DESC, region ASC
            LIMIT 1
            """
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "region": str(row["region"]),
            "revenue": float(row["revenue"]),
            "transaction_count": int(row["transaction_count"]),
        }

    def revenue_change(self, start_month: str, end_month: str) -> dict[str, int | float | str]:
        rows = self._query(
            """
            SELECT strftime('%Y-%m', order_date) AS month,
                   COALESCE(SUM(sales), 0) AS revenue
            FROM transactions
            WHERE returned = 0
              AND strftime('%Y-%m', order_date) IN (?, ?)
            GROUP BY strftime('%Y-%m', order_date)
            """,
            (start_month, end_month),
        )
        revenues = {str(row["month"]): float(row["revenue"]) for row in rows}
        start_revenue = revenues.get(start_month, 0.0)
        end_revenue = revenues.get(end_month, 0.0)
        change = end_revenue - start_revenue
        percentage = (
            (change / start_revenue) * 100 if start_revenue != 0 else None
        )
        return {
            "start_month": start_month,
            "start_revenue": start_revenue,
            "end_month": end_month,
            "end_revenue": end_revenue,
            "change": change,
            "percentage_change": percentage,
        }
