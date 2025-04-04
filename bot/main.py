import discord
from discord.ext import commands
from flask import Flask, request, jsonify
import os
from threading import Thread

# Get your Discord bot token and channel IDs from environment variables
DISCORD_TOKEN = os.getenv("FIDES_TOKEN")
COMMITS_CHANNEL_ID = 1357567489126568066  # Channel ID for commits
PULL_REQUESTS_CHANNEL_ID = 1357567373250658347  # Channel ID for pull requests
ROLE_ID = 1357602019266789437  # Role ID to mention

app = Flask(__name__)

# Initialize bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Flask route to handle GitHub webhook (synchronous)
@app.route("/github", methods=["POST"])
def github_webhook():
    data = request.json

    # Handle push events (commits)
    if "commits" in data:
        for commit in data["commits"]:
            message = (
                f"📌 **New Commit in {data['repository']['full_name']}**\n"
                f"📝 **Message:** {commit['message']}\n"
                f"👤 **Author:** {commit['author']['name']}\n"
                f"🔗 [View Commit]({commit['url']})"
            )
            # Schedule the async Discord call
            bot.loop.create_task(send_message_to_discord(message, COMMITS_CHANNEL_ID))

    # Handle pull request events
    if "pull_request" in data:
        pr = data["pull_request"]
        message = (
            f"📌 **New Pull Request in {data['repository']['full_name']}**\n"
            f"📝 **Title:** {pr['title']}\n"
            f"👤 **Opened by:** {pr['user']['login']}\n"
            f"🔗 [View Pull Request]({pr['html_url']})"
        )
        # Schedule the async Discord call
        bot.loop.create_task(send_message_to_discord(message, PULL_REQUESTS_CHANNEL_ID))

    return jsonify({"status": "success"}), 200

# Asynchronous function to send message to Discord with embeds
async def send_message_to_discord(message, channel_id):
    channel = bot.get_channel(channel_id)
    if channel:
        # Create embed message
        embed = discord.Embed(
            title="GitHub Notification",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text="GitHub Webhook")
        
        # Create the mention for the role
        role_mention = f"<@&{ROLE_ID}>"
        
        # Send the message to the channel
        await channel.send(content=role_mention, embed=embed)
    else:
        print(f"Channel with ID {channel_id} not found.")

# Start the Flask app in a separate thread
def start_flask():
    app.run(host="0.0.0.0", port=5000)

Thread(target=start_flask).start()

# Run the Discord bot
bot.run(DISCORD_TOKEN)
