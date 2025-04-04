from flask import Flask, request, jsonify
import requests
import os

URL_1 = os.getenv("URL_1")
URL_2 = os.getenv("URL_2")


app = Flask(__name__)

DISCORD_WEBHOOKS = {
    "commits": f"{URL_1}",
    "pull_requests": f"{URL_2}",
}

@app.route("/github", methods=["POST"])
def github_webhook():
    data = request.json

    # Handle commit events
    if "commits" in data:
        for commit in data["commits"]:
            message = (
                f"📌 **New Commit in {data['repository']['full_name']}**\n"
                f"📝 **Message:** {commit['message']}\n"
                f"👤 **Author:** {commit['author']['name']}\n"
                f"🔗 [View Commit]({commit['url']})"
            )
            send_to_discord(DISCORD_WEBHOOKS["commits"], message)

    # Handle pull request events
    if "pull_request" in data:
        pr = data["pull_request"]
        message = (
            f"📌 **New Pull Request in {data['repository']['full_name']}**\n"
            f"📝 **Title:** {pr['title']}\n"
            f"👤 **Opened by:** {pr['user']['login']}\n"
            f"🔗 [View Pull Request]({pr['html_url']})"
        )
        send_to_discord(DISCORD_WEBHOOKS["pull_requests"], message)

    return jsonify({"status": "success"}), 200

def send_to_discord(webhook_url, message):
    """Send a message to Discord via webhook."""
    data = {"content": message}
    requests.post(webhook_url, json=data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
