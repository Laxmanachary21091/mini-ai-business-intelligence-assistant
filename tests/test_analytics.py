from __future__ import annotations

from pathlib import Path

from app.analytics import Analytics
from app.db import initialize_database
from app.service import QuestionError, answer_question


def test_total_revenue_excludes_returned_transactions(populated_analytics: Analytics) -> None:
    assert populated_analytics.total_revenue() == {
        "revenue": 300.0,
        "transaction_count": 3,
    }


def test_highest_revenue_product(populated_analytics: Analytics) -> None:
    assert populated_analytics.top_product() == {
        "product": "Alpha",
        "revenue": 250.0,
        "transaction_count": 2,
    }


def test_monthly_revenue_trend(populated_analytics: Analytics) -> None:
    assert populated_analytics.monthly_revenue() == [
        {"month": "2024-01", "revenue": 150.0, "transaction_count": 2},
        {"month": "2024-02", "revenue": 150.0, "transaction_count": 1},
    ]


def test_region_with_highest_sales(populated_analytics: Analytics) -> None:
    assert populated_analytics.top_region() == {
        "region": "South",
        "revenue": 200.0,
        "transaction_count": 2,
    }


def test_month_comparison(populated_analytics: Analytics) -> None:
    result = populated_analytics.revenue_change("2024-01", "2024-02")
    assert result["change"] == 0
    assert result["percentage_change"] == 0


def test_zero_starting_revenue_has_undefined_percentage(tmp_path: Path) -> None:
    analytics = Analytics(tmp_path / "empty.db")
    assert analytics.total_revenue()["revenue"] == 0
    result = analytics.revenue_change("2024-01", "2024-02")
    assert result["start_revenue"] == 0
    assert result["percentage_change"] is None
    assert analytics.top_product() is None


def test_invalid_and_missing_questions_are_reported(populated_analytics: Analytics) -> None:
    try:
        answer_question("What is the weather?", populated_analytics)
    except QuestionError as exc:
        assert exc.code == "unsupported_question"
    else:
        raise AssertionError("Unsupported question should fail")

    try:
        answer_question("Compare revenue between months", populated_analytics)
    except QuestionError as exc:
        assert exc.code == "missing_parameters"
    else:
        raise AssertionError("A comparison without months should fail")


def test_empty_database_returns_zero_revenue(tmp_path: Path) -> None:
    path = tmp_path / "empty.db"
    initialize_database(path)
    analytics = Analytics(path)
    assert analytics.total_revenue() == {"revenue": 0.0, "transaction_count": 0}
    assert analytics.monthly_revenue() == []
