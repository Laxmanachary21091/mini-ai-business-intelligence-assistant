"""Natural-language intent classification with guarded Gemini integration."""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

SUPPORTED_INTENTS = {
    "total_revenue",
    "top_product",
    "monthly_trend",
    "top_region",
    "revenue_change",
}
MONTH_PATTERN = re.compile(r"^(19|20)\d{2}-(0[1-9]|1[0-2])$")
DEFAULT_GEMINI_TIMEOUT_SECONDS = 60
MAX_GEMINI_TIMEOUT_SECONDS = 300

load_dotenv()
logger = logging.getLogger(__name__)


class TimeoutConfigurationError(ValueError):
    """The configured Gemini request timeout is outside the supported range."""


@dataclass(frozen=True)
class IntentResult:
    intent: str
    parameters: dict[str, str]
    classification_source: str
    fallback_notice: str | None = None


def _valid_month(value: Any) -> bool:
    return isinstance(value, str) and MONTH_PATTERN.fullmatch(value) is not None


def _parse_model_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    result = json.loads(cleaned)
    if not isinstance(result, dict):
        raise ValueError("Gemini response must be a JSON object")
    return result


def _gemini_timeout_seconds() -> float:
    raw_timeout = os.getenv(
        "GEMINI_TIMEOUT_SECONDS", str(DEFAULT_GEMINI_TIMEOUT_SECONDS)
    )
    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise TimeoutConfigurationError(
            "GEMINI_TIMEOUT_SECONDS must be a number from 1 to 300."
        ) from exc
    if not 1 <= timeout <= MAX_GEMINI_TIMEOUT_SECONDS:
        raise TimeoutConfigurationError(
            "GEMINI_TIMEOUT_SECONDS must be between 1 and 300."
        )
    return timeout


def _gemini_classify(question: str, api_key: str) -> dict[str, Any]:
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    prompt = f"""
Classify the user's analytics question. Return JSON only, with this exact shape:
{{"intent":"one allowed intent","parameters":{{"start_month":"YYYY-MM","end_month":"YYYY-MM"}}}}
For non-comparison intents use an empty parameters object.
Allowed intents: total_revenue, top_product, monthly_trend, top_region, revenue_change.
Use revenue_change only when the question compares two months. Use YYYY-MM month
values only when explicitly present in the question. Never return SQL or prose.
Question: {json.dumps(question)}
"""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    payload = json.dumps(
        {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}}
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(
        request, timeout=_gemini_timeout_seconds()
    ) as response:
        response_data = json.loads(response.read().decode("utf-8"))
    text = response_data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_model_json(text)


def _validate_model_result(data: dict[str, Any]) -> tuple[str, dict[str, str]]:
    intent = data.get("intent")
    if intent not in SUPPORTED_INTENTS:
        raise ValueError("Gemini returned an unsupported intent")
    raw_parameters = data.get("parameters", {})
    if not isinstance(raw_parameters, dict):
        raise ValueError("Gemini parameters must be a JSON object")
    parameters: dict[str, str] = {}
    if intent == "revenue_change":
        for name in ("start_month", "end_month"):
            value = raw_parameters.get(name)
            if value is not None:
                if not _valid_month(value):
                    raise ValueError(f"Gemini returned an invalid {name}")
                parameters[name] = value
    return intent, parameters


def _rule_based_classify(question: str) -> tuple[str, dict[str, str]]:
    text = question.casefold()
    months = re.findall(r"(?<!\d)((?:19|20)\d{2}-(?:0[1-9]|1[0-2]))(?!\d)", text)
    change_words = ("change", "difference", "compare", "comparison", "growth", "increase", "decrease", "between")

    if any(word in text for word in change_words) and (
        "revenue" in text or "sales" in text or "month" in text
    ):
        parameters: dict[str, str] = {}
        if len(months) >= 2:
            parameters = {"start_month": months[0], "end_month": months[1]}
        return "revenue_change", parameters

    if "product" in text and any(
        word in text for word in ("highest", "top", "best", "most", "leading")
    ):
        return "top_product", {}
    if any(word in text for word in ("region", "regional")) and any(
        word in text for word in ("highest", "top", "best", "most", "sales")
    ):
        return "top_region", {}
    if any(word in text for word in ("monthly", "month-by-month", "month by month", "trend")):
        return "monthly_trend", {}
    if any(
        phrase in text
        for phrase in ("total revenue", "overall revenue", "total sales", "overall sales")
    ):
        return "total_revenue", {}
    if "revenue" in text and any(
        word in text for word in ("total", "overall", "all", "entire")
    ):
        return "total_revenue", {}
    return "unsupported", {}


def classify_question(question: str) -> IntentResult:
    """Classify against an allowlist; fall back to deterministic rules as needed."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        fallback_notice = (
            "Gemini API key is missing. Add GEMINI_API_KEY to the project-root "
            ".env file and restart the app; rule-based question routing was used."
        )
        logger.warning("Gemini fallback: API key is missing")
    else:
        try:
            intent, parameters = _validate_model_result(
                _gemini_classify(question, api_key)
            )
            return IntentResult(intent, parameters, "gemini")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                reason = (
                    "Gemini rejected the API key or project permissions "
                    f"(HTTP {exc.code}). Check the key in Google AI Studio."
                )
            elif exc.code == 404:
                reason = (
                    "Gemini model was not found (HTTP 404). Check GEMINI_MODEL "
                    "against the models enabled for your API key."
                )
            elif exc.code == 429:
                reason = (
                    "Gemini request quota or rate limit was reached (HTTP 429)."
                )
            else:
                reason = f"Gemini returned HTTP {exc.code}."
            logger.warning("Gemini fallback: HTTP %s", exc.code)
            fallback_notice = reason + " Rule-based question routing was used."
        except TimeoutConfigurationError as exc:
            logger.error("Gemini fallback: %s", exc)
            fallback_notice = (
                f"{exc} Rule-based question routing was used."
            )
        except TimeoutError:
            timeout = os.getenv(
                "GEMINI_TIMEOUT_SECONDS",
                str(DEFAULT_GEMINI_TIMEOUT_SECONDS),
            )
            logger.warning("Gemini fallback: request timed out")
            fallback_notice = (
                f"Gemini did not respond within {timeout} seconds. Check your "
                "internet connection or try again later. Rule-based question "
                "routing was used."
            )
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                timeout = os.getenv(
                    "GEMINI_TIMEOUT_SECONDS",
                    str(DEFAULT_GEMINI_TIMEOUT_SECONDS),
                )
                fallback_notice = (
                    f"Gemini did not respond within {timeout} seconds. Check your "
                    "internet connection or try again later. Rule-based question "
                    "routing was used."
                )
                logger.warning("Gemini fallback: request timed out")
            else:
                logger.warning(
                    "Gemini fallback: network request failed (%s)",
                    type(exc).__name__,
                )
                fallback_notice = (
                    "Gemini could not be reached due to a network issue. Check "
                    "your internet connection or try again later. Rule-based "
                    "question routing was used."
                )
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            logger.warning(
                "Gemini fallback: invalid response or classification (%s)",
                type(exc).__name__,
            )
            fallback_notice = (
                "Gemini returned an invalid response or unsupported classification. "
                "Rule-based question routing was used."
            )

    intent, parameters = _rule_based_classify(question)
    return IntentResult(
        intent, parameters, "rule_based_fallback", fallback_notice
    )
