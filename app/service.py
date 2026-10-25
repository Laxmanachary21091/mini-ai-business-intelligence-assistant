"""Application service shared by the FastAPI and Streamlit interfaces."""

from __future__ import annotations

import re
from typing import Any

from app.analytics import Analytics
from app.nlq import IntentResult, classify_question


class QuestionError(ValueError):
    """A user question is unsupported or lacks required information."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        query_intent: str | None = None,
        classification_source: str | None = None,
        fallback_notice: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.query_intent = query_intent
        self.classification_source = classification_source
        self.fallback_notice = fallback_notice


def _valid_month(month: str) -> bool:
    return re.fullmatch(r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])", month) is not None


def answer_question(question: str, analytics: Analytics | None = None) -> dict[str, Any]:
    """Return a structured result without accepting or executing model-generated SQL."""
    cleaned_question = question.strip()
    if not cleaned_question:
        raise QuestionError("invalid_question", "Please enter a question.")
    classifier: IntentResult = classify_question(cleaned_question)
    intent = classifier.intent
    if intent not in {
        "total_revenue",
        "top_product",
        "monthly_trend",
        "top_region",
        "revenue_change",
    }:
        raise QuestionError(
            "unsupported_question",
            "I can answer questions about total revenue, the top product, "
            "monthly revenue trends, the top region, or revenue changes "
            "between two YYYY-MM months.",
            query_intent=intent,
            classification_source=classifier.classification_source,
            fallback_notice=classifier.fallback_notice,
        )

    engine = analytics or Analytics()
    parameters = classifier.parameters
    if intent == "revenue_change":
        start_month = parameters.get("start_month")
        end_month = parameters.get("end_month")
        if not start_month or not end_month:
            raise QuestionError(
                "missing_parameters",
                "Please specify two months in YYYY-MM format, for example "
                "'revenue change between 2024-01 and 2024-02'.",
                query_intent=intent,
                classification_source=classifier.classification_source,
                fallback_notice=classifier.fallback_notice,
            )
        if not _valid_month(start_month) or not _valid_month(end_month):
            raise QuestionError(
                "invalid_parameters",                 "Both months must use the YYYY-MM format.",
                query_intent=intent,
                classification_source=classifier.classification_source,
                fallback_notice=classifier.fallback_notice,
            )
        figures = engine.revenue_change(start_month, end_month)
        percentage = figures["percentage_change"]
        percentage_text = (
            "percentage change is undefined because starting-month revenue is zero."
            if percentage is None
            else f"percentage change is {percentage:.2f}%."
        )
        answer = (
            f"Revenue changed by {figures['change']:,.2f} from "
            f"{start_month} ({figures['start_revenue']:,.2f}) to "
            f"{end_month} ({figures['end_revenue']:,.2f}); {percentage_text}"
        )
    elif intent == "total_revenue":
        figures = engine.total_revenue()
        answer = f"Total eligible revenue is {figures['revenue']:,.2f}."
    elif intent == "top_product":
        figures = engine.top_product()
        answer = (
            "No eligible transactions were found."
            if figures is None
            else f"{figures['product']} has the highest revenue at "
            f"{figures['revenue']:,.2f}."
        )
    elif intent == "monthly_trend":
        figures = engine.monthly_revenue()
        answer = (
            "No eligible transactions were found for the monthly trend."
            if not figures
            else f"Monthly revenue is available for {len(figures)} month(s)."
        )
    else:
        figures = engine.top_region()
        answer = (
            "No eligible transactions were found."
            if figures is None
            else f"{figures['region']} has the highest sales at "
            f"{figures['revenue']:,.2f}."
        )

    return {
        "status": "ok",
        "answer": answer,
        "supporting_figures": figures,
        "query_intent": intent,
        "classification_source": classifier.classification_source,
        "fallback_notice": classifier.fallback_notice,
        "error": None,
    }
