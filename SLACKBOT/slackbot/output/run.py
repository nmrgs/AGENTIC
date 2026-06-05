"""Output pipeline — formats engine results for Slack."""

from typing import Any

from slackbot.output.formatter import format_response, FormattedOutput


def run(question: str, raw_response: Any) -> FormattedOutput:
    """Format the raw PandasAI response for Slack.

    Parameters
    ----------
    question : str
        The original user question.
    raw_response : Any
        The raw PandasAI response object.

    Returns
    -------
    FormattedOutput
        Ready-to-send Slack message components.
    """
    return format_response(question, raw_response)
