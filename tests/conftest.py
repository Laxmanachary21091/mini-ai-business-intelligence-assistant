from __future__ import annotations

from pathlib import Path

import pytest

from app.analytics import Analytics
from app.ingestion import ingest_csv


@pytest.fixture(autouse=True)
def disable_real_gemini_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep automated tests deterministic and prevent calls using local .env secrets."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture
def populated_analytics(tmp_path: Path) -> Analytics:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "transaction_id,order_date,product,region,sales,returned\n"
        "1,2024-01-10,Alpha,North,100,false\n"
        "2,2024-01-20,Beta,South,50,false\n"
        "3,2024-02-10,Alpha,South,150,false\n"
        "4,2024-02-15,Gamma,North,500,true\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "sales.db"
    ingest_csv(csv_path, db_path)
    return Analytics(db_path)
