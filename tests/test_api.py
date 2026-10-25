from __future__ import annotations

from fastapi.testclient import TestClient

from app import api as api_module
from app.analytics import Analytics


def test_ask_api_returns_structured_analytics(
    populated_analytics: Analytics, monkeypatch
) -> None:
    monkeypatch.setattr(api_module, "analytics", populated_analytics)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    response = TestClient(api_module.app).post(
        "/ask", json={"question": "What is the total revenue?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["query_intent"] == "total_revenue"
    assert body["supporting_figures"]["revenue"] == 300.0
    assert body["classification_source"] == "rule_based_fallback"
    assert "API key is missing" in body["fallback_notice"]


def test_ask_api_reports_invalid_question_as_structured_error(
    populated_analytics: Analytics, monkeypatch
) -> None:
    monkeypatch.setattr(api_module, "analytics", populated_analytics)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    response = TestClient(api_module.app).post(
        "/ask", json={"question": "Tell me a joke"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "unsupported_question"
    assert body["classification_source"] == "rule_based_fallback"
    assert body["fallback_notice"]


def test_gemini_auth_failure_has_safe_actionable_fallback_notice(monkeypatch) -> None:
    from urllib.error import HTTPError

    from app import nlq

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def reject_key(question: str, api_key: str) -> dict:
        raise HTTPError(
            "https://generativelanguage.googleapis.com/test",
            403,
            "Forbidden",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(nlq, "_gemini_classify", reject_key)

    result = nlq.classify_question("What is the total revenue?")

    assert result.classification_source == "rule_based_fallback"
    assert "HTTP 403" in (result.fallback_notice or "")
    assert "Check the key" in (result.fallback_notice or "")
    assert "test-key" not in (result.fallback_notice or "")


def test_gemini_generation_uses_configured_timeout(monkeypatch) -> None:
    import io
    import json
    from unittest.mock import patch

    from app import nlq

    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "75")
    response_body = json.dumps(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"intent":"total_revenue","parameters":{}}'
                                )
                            }
                        ]
                    }
                }
            ]
        }
    ).encode("utf-8")

    with patch(
        "app.nlq.urllib.request.urlopen",
        return_value=io.BytesIO(response_body),
    ) as urlopen:
        result = nlq._gemini_classify("What is the total revenue?", "test-key")

    assert result == {"intent": "total_revenue", "parameters": {}}
    assert urlopen.call_args.kwargs["timeout"] == 75


def test_gemini_timeout_notice_recommends_waiting_or_network_check(
    monkeypatch,
) -> None:
    from app import nlq

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "60")

    def timeout(question: str, api_key: str) -> dict:
        raise TimeoutError

    monkeypatch.setattr(nlq, "_gemini_classify", timeout)

    result = nlq.classify_question("What is the total revenue?")

    assert result.classification_source == "rule_based_fallback"
    assert "60 seconds" in (result.fallback_notice or "")
    assert "internet connection" in (result.fallback_notice or "")
