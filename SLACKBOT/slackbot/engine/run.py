"""Engine pipeline — routes question to relevant tables and queries via PandasAI."""

from dataclasses import dataclass

from slackbot.engine.router import route
from slackbot.engine.agent import query


@dataclass
class EngineResult:
    answer: str
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
        The answer from PandasAI and which tables were used.
    """
    tables = route(question)
    answer = query(question, tables)

    return EngineResult(
        answer=answer,
        tables_used=tables,
    )
