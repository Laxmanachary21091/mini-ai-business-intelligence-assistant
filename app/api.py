"""FastAPI endpoints for asking analytics questions."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.analytics import Analytics
from app.db import database_path, initialize_database
from app.service import QuestionError, answer_question

logger = logging.getLogger(__name__)
initialize_database(database_path())
analytics = Analytics(database_path())

app = FastAPI(
    title="Mini AI Business Intelligence Assistant",
    description="Natural-language access to fixed, read-only sales analytics.",
    version="1.0.0",
)


class AskRequest(BaseModel):
    question: str = Field(max_length=1000)


class AskResponse(BaseModel):
    status: str
    answer: str
    supporting_figures: Any | None = None
    query_intent: str | None = None
    classification_source: str | None = None
    fallback_notice: str | None = None
    error: dict[str, str] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse | JSONResponse:
    try:
        result = answer_question(request.question, analytics)
        return AskResponse(**result)
    except QuestionError as exc:
        return JSONResponse(
            status_code=422,
            content=AskResponse(
                status="error",
                answer=str(exc),
                query_intent=exc.query_intent,
                classification_source=exc.classification_source,
                fallback_notice=exc.fallback_notice,
                error={"code": exc.code, "message": str(exc)},
            ).model_dump(),
        )
    except Exception:
        logger.exception("Unexpected failure handling /ask")
        return JSONResponse(
            status_code=500,
            content=AskResponse(
                status="error",
                answer="An unexpected error occurred while processing the question.",
                error={
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                },
            ).model_dump(),
        )
