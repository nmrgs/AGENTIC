"""Engine pipeline — routes question to relevant tables and queries via PandasAI."""

from dataclasses import dataclass
from typing import Any

from slackbot.engine.router import route
from slackbot.engine.agent import query


@dataclass
class EngineResult:
    raw_response: Any
    tables_used: list[str]


def run(question: str) -> EngineResult:
    """Run the full engine pipeline: route to tables then query.

    Parameters
    ----------
    question : str
        The cleaned, validated user question.

    Returns
    -------
    EngineResult
        The raw PandasAI response and which tables were used.
    """
    tables = route(question)
    response = query(question, tables)

    return EngineResult(
        raw_response=response,
        tables_used=tables,
    )
