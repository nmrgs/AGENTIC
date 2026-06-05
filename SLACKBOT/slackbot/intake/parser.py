"""Parser module — minimal cleanup of raw Slack message text."""

import re


_MENTION_RE = re.compile(r"<@[A-Z0-9]+>")


def parse(raw_text: str) -> str:
    """Strip bot mention and normalize whitespace.

    Parameters
    ----------
    raw_text : str
        The raw message text from Slack (includes <@BOT_ID> mention).

    Returns
    -------
    str
        Cleaned question text ready for guardrails.
    """
    text = _MENTION_RE.sub("", raw_text)
    text = " ".join(text.split())
    return text.strip()
