"""Streamlit dashboard for the Mini AI Business Intelligence Assistant."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analytics import Analytics
from app.service import QuestionError, answer_question

st.set_page_config(
    page_title="Sales BI Assistant",
    page_icon="📊",
    layout="wide",
)
st.title("Mini AI Business Intelligence Assistant")
st.caption(
    "Ask a supported sales question. Answers are calculated from SQLite; "
    "Gemini classifies questions when configured."
)

examples = [
    "What is the total revenue?",
    "Which product has the highest revenue?",
    "Show the monthly revenue trend.",
    "Which region has the highest sales?",
    "What is the revenue change between 2026-01 and 2026-02?",
]
question = st.text_input(
    "Ask a question",
    placeholder="e.g. Which product has the highest revenue?",
)
selected_example = st.selectbox("Example questions", ["Choose an example", *examples])
if selected_example != "Choose an example" and st.button("Use example"):
    question = selected_example
    st.session_state["question"] = question
if question:
    st.session_state["question"] = question

submitted_question = st.session_state.get("question", "")
if st.button("Ask", type="primary") and submitted_question:
    try:
        result = answer_question(submitted_question, Analytics())
        st.success(result["answer"])
        if result["fallback_notice"]:
            st.info(result["fallback_notice"])
        st.caption(
            f"Intent: `{result['query_intent']}` · "
            f"Classification: `{result['classification_source']}`"
        )
        figures = result["supporting_figures"]
        if isinstance(figures, list):
            st.dataframe(pd.DataFrame(figures), use_container_width=True)
        elif isinstance(figures, dict):
            st.dataframe(
                pd.DataFrame([figures]).T.rename(columns={0: "Value"}),
                use_container_width=True,
            )
    except QuestionError as exc:
        st.error(str(exc))
        if exc.fallback_notice:
            st.info(exc.fallback_notice)
    except Exception:
        st.error(
            "The question could not be processed. Check that the database has "
            "been initialized and review the API/UI logs."
        )

st.divider()
st.subheader("Monthly revenue trend")
try:
    monthly_data = Analytics().monthly_revenue()
    if monthly_data:
        trend = pd.DataFrame(monthly_data).set_index("month")
        st.line_chart(trend["revenue"])
        st.dataframe(pd.DataFrame(monthly_data), use_container_width=True)
    else:
        st.info(
            "No eligible transaction data is loaded yet. Ingest your CSV to "
            "populate the monthly trend."
        )
except Exception:
    st.error(
        "Monthly trend is unavailable. Confirm the database path and ingestion status."
    )
