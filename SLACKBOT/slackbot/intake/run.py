"""Intake pipeline — chains parser and guardrails into a single entry point."""

from dataclasses import dataclass

from slackbot.intake.parser import parse
from slackbot.intake.guardrails import check


@dataclass
class IntakeResult:
    question: str
    allowed: bool
    rejection_reason: str | None


def run(raw_text: str) -> IntakeResult:
    """Run the full intake pipeline: parse then validate.

    Parameters
    ----------
    raw_text : str
        Raw message text from Slack (includes bot mention).

    Returns
    -------
    IntakeResult
        Cleaned question, whether it's allowed, and rejection reason if not.
    """
    question = parse(raw_text)

    if not question:
        return IntakeResult(
            question="",
            allowed=False,
            rejection_reason="I didn't receive a question. Please mention me with a question about your data.",
        )

    result = check(question)

    return IntakeResult(
        question=question,
        allowed=result.allowed,
        rejection_reason=result.reason if not result.allowed else None,
    )
