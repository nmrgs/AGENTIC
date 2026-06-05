"""Output formatter — converts raw PandasAI responses into Slack-friendly messages."""

import tempfile
from dataclasses import dataclass
from typing import Any

import pandas as pd
from langchain_openai import ChatOpenAI

from pandasai.core.response.chart import ChartResponse
from pandasai.core.response.dataframe import DataFrameResponse
from pandasai.core.response.number import NumberResponse


@dataclass
class FormattedOutput:
    summary: str
    text_data: str | None
    chart_path: str | None


def _format_dataframe(df: pd.DataFrame) -> str:
    """Format a DataFrame as a Slack code block."""
    return f"```\n{df.to_string(index=False)}\n```"


def _save_chart(response: ChartResponse) -> str:
    """Save chart to a temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    response.save(tmp.name)
    return tmp.name


def _generate_summary(question: str, raw_data: str) -> str:
    """Use LLM to generate a plain English summary of the result."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    response = llm.invoke([
        {
            "role": "system",
            "content": (
                "You are a data analyst assistant. Given a user's question and the raw query result, "
                "write a concise plain English summary (2-3 sentences max). "
                "Highlight the key insight or answer. Do not repeat the raw data."
            ),
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nResult:\n{raw_data}",
        },
    ])

    return response.content.strip()


def format_response(question: str, raw_response: Any) -> FormattedOutput:
    """Detect response type and format for Slack.

    Parameters
    ----------
    question : str
        The original user question.
    raw_response : Any
        The raw PandasAI response object.

    Returns
    -------
    FormattedOutput
        Summary, optional text data, and optional chart path.
    """
    text_data = None
    chart_path = None
    raw_data_str = ""

    if isinstance(raw_response, ChartResponse):
        chart_path = _save_chart(raw_response)
        raw_data_str = "A chart was generated."
        summary = _generate_summary(question, raw_data_str)

    elif isinstance(raw_response, DataFrameResponse):
        df = raw_response.value
        raw_data_str = df.to_string(index=False)
        text_data = _format_dataframe(df)
        summary = _generate_summary(question, raw_data_str)

    elif isinstance(raw_response, NumberResponse):
        raw_data_str = str(raw_response.value)
        text_data = f"*{raw_data_str}*"
        summary = _generate_summary(question, raw_data_str)

    else:
        # Plain string or unknown type
        raw_data_str = str(raw_response)
        text_data = raw_data_str
        summary = _generate_summary(question, raw_data_str)

    return FormattedOutput(
        summary=summary,
        text_data=text_data,
        chart_path=chart_path,
    )
