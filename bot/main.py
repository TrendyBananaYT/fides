import discord
from discord.ext import commands
from flask import Flask, request, jsonify
import os
from threading import Thread
from datetime import datetime, timezone

# Environment variables and channel/role IDs
DISCORD_TOKEN = os.getenv("FIDES_TOKEN")
COMMITS_CHANNEL_ID = 1357567489126568066       # Channel ID for commits
PULL_REQUESTS_CHANNEL_ID = 1357567373250658347  # Channel ID for pull requests
ROLE_ID = 1357602019266789437                   # Role ID to mention

app = Flask(__name__)

# Initialize bot with default intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Synchronous Flask route (using bot.loop.create_task for async calls)
@app.route("/github", methods=["POST"])
def github_webhook():
    data = request.json

    # Handle commit events (push)
    if "commits" in data:
        for commit in data["commits"]:
            repository_name = data["repository"]["full_name"]
            repository_url = data["repository"].get("html_url", "")
            # Format repository as a clickable link
            repo_link = f"[{repository_name}]({repository_url})" if repository_url else repository_name

            commit_message = commit["message"]
            commit_url = commit["url"]
            # Format commit URL as a shortened link
            commit_link = f"[View Commit]({commit_url})"
            
            # For commit author, use username if available
            if commit["author"].get("username"):
                author_link = f"[{commit['author']['name']}](https://github.com/{commit['author']['username']})"
            else:
                author_link = commit["author"]["name"]

            timestamp = datetime.now(timezone.utc).isoformat() + " UTC"

            log_details = (
                f"**Repository:** {repo_link}\n"
                f"**Author:** {author_link}\n"
                f"**Message:** {commit_message}\n"
                f"**Commit:** {commit_link}\n"
                f"**Timestamp:** {timestamp}"
            )
            bot.loop.create_task(send_message_to_discord(
                event_type="Commit",
                log_details=log_details,
                channel_id=COMMITS_CHANNEL_ID
            ))

    # Handle pull request events
    if "pull_request" in data:
        pr = data["pull_request"]
        repository_name = data["repository"]["full_name"]
        repository_url = data["repository"].get("html_url", "")
        repo_link = f"[{repository_name}]({repository_url})" if repository_url else repository_name

        pr_title = pr["title"]
        pr_url = pr["html_url"]
        pr_link = f"[View PR]({pr_url})"
        pr_author = pr["user"]["login"]
        pr_author_url = pr["user"].get("html_url", f"https://github.com/{pr_author}")
        author_link = f"[{pr_author}]({pr_author_url})"

        timestamp = datetime.now(timezone.utc).isoformat() + " UTC"

        log_details = (
            f"**Repository:** {repo_link}\n"
            f"**Title:** {pr_title}\n"
            f"**Opened by:** {author_link}\n"
            f"**PR:** {pr_link}\n"
            f"**Timestamp:** {timestamp}"
        )
        bot.loop.create_task(send_message_to_discord(
            event_type="Pull Request",
            log_details=log_details,
            channel_id=PULL_REQUESTS_CHANNEL_ID
        ))

    return jsonify({"status": "success"}), 200

# Asynchronous function to send the detailed embed to Discord
async def send_message_to_discord(event_type, log_details, channel_id):
    channel = bot.get_channel(channel_id)
    if channel is None:
        print(f"Channel with ID {channel_id} not found!")
        return

    embed = discord.Embed(
        title=f"🔔 New GitHub {event_type} Notification",
        description="A GitHub event has been triggered. Details are shown below:",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    # Add a field with the detailed log formatted as a code block for clarity
    embed.add_field(name="Event Details", value=f"```{log_details}```", inline=False)
    embed.set_footer(text="GitHub Webhook")

    await channel.send(
        embed=embed,
        content=f"<@&{ROLE_ID}>",
        allowed_mentions=discord.AllowedMentions(roles=True)
    )

# Run the Flask app in a separate thread
def start_flask():
    app.run(host="0.0.0.0", port=5000)

Thread(target=start_flask).start()

# Run the Discord bot
bot.run(DISCORD_TOKEN)
