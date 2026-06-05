"""PandasAI Agent wrapper — loads datasets and queries them."""

import os

import pandasai as pai
from pandasai import Agent
from pandasai_litellm.litellm import LiteLLM


def _configure_llm():
    """Configure PandasAI to use OpenAI via LiteLLM."""
    llm = LiteLLM(model="gpt-4.1-mini")
    pai.config.set({"llm": llm})


def query(question: str, tables: list[str]) -> str:
    """Load the specified datasets and ask PandasAI the question.

    Parameters
    ----------
    question : str
        The cleaned user question.
    tables : list[str]
        List of table names to load (e.g., ["users", "payments"]).

    Returns
    -------
    str
        The response from PandasAI (text, DataFrame string, or chart path).
    """
    _configure_llm()

    datasets = []
    for table in tables:
        dataset = pai.load(f"public/{table}")
        datasets.append(dataset)

    agent = Agent(datasets)
    response = agent.chat(question)

    return str(response)
