import os

import matplotlib
matplotlib.use("Agg")

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from slackbot.intake import run as intake_run
from slackbot.engine import run as engine_run
from slackbot.output import run as output_run
from slackbot.engine.setup_datasets import ensure_datasets

load_dotenv()
ensure_datasets()

app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.event("app_mention")
def handle_mention(event, say):
    """Process a user question through the intake pipeline (channel mentions)."""
    _process_question(event, say)


@app.event("message")
def handle_dm(event, say):
    """Process direct messages to the bot."""
    # Ignore bot's own messages to avoid loops
    if event.get("subtype") == "bot_message" or event.get("bot_id"):
        return
    # Only respond in DMs (channel type "im")
    if event.get("channel_type") != "im":
        return
    _process_question(event, say)


def _process_question(event, say):
    """Run the full pipeline: intake → engine → output."""
    raw_text = event.get("text", "")
    channel = event.get("channel")

    result = intake_run(raw_text)

    if not result.allowed:
        say(f":x: {result.rejection_reason}")
        return

    say(f":hourglass_flowing_sand: Looking into: _{result.question}_")

    try:
        engine_result = engine_run(result.question)
        formatted = output_run(result.question, engine_result.raw_response)

        # Send the plain English summary
        say(formatted.summary)

        # Send text data (table or number) if present
        if formatted.text_data:
            say(formatted.text_data)

        # Upload chart image if present
        if formatted.chart_path:
            app.client.files_upload_v2(
                channel=channel,
                file=formatted.chart_path,
                title="Chart",
                initial_comment="",
            )

    except Exception as e:
        say(f":warning: Something went wrong while processing your question: {e}")


def main():
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("Bot is running...")
    handler.start()


if __name__ == "__main__":
    main()
