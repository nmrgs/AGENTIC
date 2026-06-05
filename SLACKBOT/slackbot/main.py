import os

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.event("app_mention")
def handle_mention(event, say):
    """Echo back when the bot is mentioned to verify it's alive."""
    user = event.get("user")
    text = event.get("text", "")
    say(f"Hey <@{user}>, I received: _{text}_")


def main():
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("Bot is running...")
    handler.start()


if __name__ == "__main__":
    main()
