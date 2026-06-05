import os

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from slackbot.intake import run as intake_run
from slackbot.engine import run as engine_run
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
    """Run the intake pipeline, then engine if allowed."""
    raw_text = event.get("text", "")

    result = intake_run(raw_text)

    if not result.allowed:
        say(f":x: {result.rejection_reason}")
        return

    say(f":hourglass_flowing_sand: Looking into: _{result.question}_")

    try:
        engine_result = engine_run(result.question)
        say(engine_result.answer)
    except Exception as e:
        say(f":warning: Something went wrong while processing your question: {e}")


def main():
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("Bot is running...")
    handler.start()


if __name__ == "__main__":
    main()
