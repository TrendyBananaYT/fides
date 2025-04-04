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
            repository = data["repository"]["full_name"]
            commit_message = commit["message"]
            commit_author = commit["author"]["name"]
            commit_url = commit["url"]
            log_details = (
                f"Repository: {repository}\n"
                f"Author: {commit_author}\n"
                f"Message: {commit_message}\n"
                f"Commit URL: {commit_url}\n"
                f"Timestamp: {datetime.now(timezone.utc).isoformat()} UTC"
            )
            bot.loop.create_task(send_message_to_discord(
                event_type="Commit",
                log_details=log_details,
                channel_id=COMMITS_CHANNEL_ID
            ))

    # Handle pull request events
    if "pull_request" in data:
        pr = data["pull_request"]
        repository = data["repository"]["full_name"]
        pr_title = pr["title"]
        pr_author = pr["user"]["login"]
        pr_url = pr["html_url"]
        log_details = f'''
            Repository: {repository}\n"
            Title: {pr_title}\n"
            Opened by: {pr_author}\n"
            PR URL: {pr_url}\n"
            Timestamp: {datetime.datetime.utcnow().isoformat()} UT
        '''

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
        title=f"New GitHub {event_type} Notification",
        description="Below is the detailed log of the event:",
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Details", value=f"```{log_details}```", inline=False)
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
