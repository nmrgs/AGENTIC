"""Output subsystem — formats raw results into Slack-friendly messages."""

from slackbot.output.run import run
from slackbot.output.formatter import FormattedOutput

__all__ = ["run", "FormattedOutput"]
