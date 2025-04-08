import discord
from discord.ext import commands
from flask import Flask, request, jsonify
import os
from threading import Thread
from datetime import datetime, timezone
import requests
import json
import re

# Environment variables and channel/role IDs
DISCORD_TOKEN = os.getenv("FIDES_TOKEN")
COMMITS_CHANNEL_ID = 1357567489126568066       # Channel ID for commits
PULL_REQUESTS_CHANNEL_ID = 1357567373250658347  # Channel ID for pull requests
ROLE_ID = 1357602019266789437                   # Role ID to mention

# Global default owner (used if a server hasn't set its owner)
default_owner = "TrendyBananaYT"
# Use an absolute path to ensure the JSON file is in the same directory as this script
owners_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "owners.json")
owners_data = {}

# Load owners from JSON file at startup
def load_owners():
    global owners_data
    if os.path.exists(owners_file):
        with open(owners_file, "r") as f:
            try:
                owners_data = json.load(f)
                print(f"Loaded owners data from {owners_file}: {owners_data}")
            except json.JSONDecodeError:
                print("Error decoding JSON; starting with an empty owners dictionary.")
                owners_data = {}
    else:
        owners_data = {}
        print("No owners file found; starting with an empty owners dictionary.")

# Save owners data to JSON file
def save_owners():
    try:
        with open(owners_file, "w") as f:
            json.dump(owners_data, f, indent=4)
        print(f"Owners data saved to {owners_file}")
        print(f"Current owners data: {owners_data}")
    except Exception as e:
        print(f"Error saving owners data: {e}")

load_owners()

app = Flask(__name__)

# Initialize bot with default intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(e)

def get_discord_timestamp(dt: datetime) -> str:
    unix_time = int(dt.timestamp())
    return f"<t:{unix_time}:F>"

@app.route("/github", methods=["GET", "POST"])
def github_webhook():
    if request.method == "GET":
        # Inform users that this endpoint expects POST requests (e.g., GitHub webhook events)
        return jsonify({
            "message": "This endpoint is intended to receive POST requests from GitHub Webhooks."
        }), 200

    # For POST requests, proceed with processing the webhook payload
    data = request.json
    # --- [rest of your webhook code remains the same] ---
    if "commits" in data:
        for commit in data["commits"]:
            repository_name = data["repository"]["full_name"]
            repository_url = data["repository"].get("html_url", "")
            repo_link = f"[{repository_name}]({repository_url})" if repository_url else repository_name

            commit_message = commit["message"]
            commit_url = commit["url"]
            commit_link = f"[View Commit]({commit_url})"

            if commit["author"].get("username"):
                author_link = f"[{commit['author']['name']}](https://github.com/{commit['author']['username']})"
            else:
                author_link = commit["author"]["name"]

            now = datetime.now(timezone.utc)
            discord_ts = get_discord_timestamp(now)

            log_details = (
                f"**Repository:** {repo_link}\n\n"
                f"**Author:** {author_link}\n\n"
                f"**Message:** {commit_message}\n\n"
                f"**Commit:** {commit_link}\n\n"
                f"**Timestamp:** {discord_ts}"
            )
            bot.loop.create_task(send_message_to_discord(
                event_type="Commit",
                log_details=log_details,
                channel_id=COMMITS_CHANNEL_ID
            ))

    if "pull_request" in data:
        pr = data["pull_request"]
        action = data.get("action")
        merged = pr.get("merged", False)
        repository_name = data["repository"]["full_name"]
        repository_url = data["repository"].get("html_url", "")
        repo_link = f"[{repository_name}]({repository_url})" if repository_url else repository_name

        pr_title = pr["title"]
        pr_url = pr["html_url"]
        pr_link = f"[View PR]({pr_url})"
        pr_author = pr["user"]["login"]
        pr_author_url = pr["user"].get("html_url", f"https://github.com/{pr_author}")
        author_link = f"[{pr_author}]({pr_author_url})"

        now = datetime.now(timezone.utc)
        discord_ts = get_discord_timestamp(now)

        if action == "closed" and merged:
            log_details = (
                f"**Repository:** {repo_link}\n\n"
                f"**Title:** {pr_title}\n\n"
                f"**Merged by:** {author_link}\n\n"
                f"**PR:** {pr_link}\n\n"
                f"**Timestamp:** {discord_ts}"
            )
            bot.loop.create_task(send_message_to_discord(
                event_type="Merge",
                log_details=log_details,
                channel_id=COMMITS_CHANNEL_ID
            ))
        else:
            log_details = (
                f"**Repository:** {repo_link}\n\n"
                f"**Title:** {pr_title}\n\n"
                f"**Opened by:** {author_link}\n\n"
                f"**PR:** {pr_link}\n\n"
                f"**Timestamp:** {discord_ts}"
            )
            bot.loop.create_task(send_message_to_discord(
                event_type="Pull Request",
                log_details=log_details,
                channel_id=PULL_REQUESTS_CHANNEL_ID
            ))

    return jsonify({"status": "success"}), 200


async def send_message_to_discord(event_type, log_details, channel_id):
    channel = bot.get_channel(channel_id)
    if channel is None:
        print(f"Channel with ID {channel_id} not found!")
        return

    embed = discord.Embed(
        title=f"🔔 New GitHub {event_type} Notification",
        description="A GitHub event has been triggered. See details below:",
        color=discord.Color.brand_green(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Event Details", value=log_details, inline=False)
    embed.set_footer(text="GitHub Webhook")

    await channel.send(
        embed=embed,
        content=f"<@&{ROLE_ID}>",
        allowed_mentions=discord.AllowedMentions(roles=True)
    )

# ===============================
# Slash Command: /setowner
# ===============================
@bot.tree.command(name="setowner", description="Set the repository owner for this server")
async def setowner(interaction: discord.Interaction, owner_name: str):
    guild_id = str(interaction.guild.id)
    owners_data[guild_id] = owner_name
    save_owners()
    await interaction.response.send_message(f"Owner set to `{owner_name}` for this server.", ephemeral=True)

# ===============================
# Slash Command: /announce
# ===============================

@bot.tree.command(name="announce", description="Make an embedded announcement in a specified channel.")
async def announce(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    title: str = None,
    description: str = None,
    fields: str = None,
    footer: str = None
):
    """
    Sends an embedded announcement to a specified channel.

    Parameters:
      - channel: The channel where the announcement will be posted.
      - title: (Optional) The title of the announcement. Literal "\n" will be converted to newlines.
      - description: (Optional) The main description text. Literal "\n" will be converted to newlines.
      - fields: (Optional) A string where each field is separated by the delimiter "~\n+~".
                Each field should be in the format "Field Name:Field Value".
                Literal "\n" in field names/values will be converted to actual newlines.
      - footer: (Optional) A footer text for the embed. Literal "\n" will be converted to newlines.
    """
    # Replace literal "\n" with actual newline characters in title and description
    embed = discord.Embed(
        title=title.replace("\\n", "\n") if title else "",
        description=description.replace("\\n", "\n") if description else "",
        color=discord.Color.blurple()
    )
    
    if fields:
        # Split using a regex that splits on ~ followed by one or more newlines followed by ~
        field_list = re.split(r'~\n+~', fields)
        for field in field_list:
            if ":" in field:
                name, value = field.split(":", 1)
                name = name.strip().replace("\\n", "\n")
                value = value.strip().replace("\\n", "\n")
                embed.add_field(name=name, value=value, inline=False)
            else:
                embed.add_field(name=field.strip().replace("\\n", "\n"), value="\u200b", inline=False)
    
    if footer:
        embed.set_footer(text=footer.replace("\\n", "\n"))
    
    await channel.send(embed=embed)
    await interaction.response.send_message(f"Announcement sent to {channel.mention}", ephemeral=True)



# -------------------------------
# Commit Paginator and Selector (Select Menu Only)
# -------------------------------

class CommitSelectView(discord.ui.View):
    def __init__(self, commits, owner, repo, url):
        super().__init__(timeout=180)
        self.commits = commits
        self.owner = owner
        self.repo = repo
        self.url = url

        # Build options for up to 25 commits (Discord limit)
        options = []
        for i, commit in enumerate(commits[:25]):
            short_sha = commit["sha"][:7]
            message = commit["commit"]["message"].splitlines()[0]
            description = message if len(message) <= 50 else message[:47] + "..."
            options.append(discord.SelectOption(label=short_sha, description=description, value=str(i)))
        
        select_menu = discord.ui.Select(
            placeholder="Select a commit to view its details...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="commit_select"
        )
        select_menu.callback = self.select_callback
        self.add_item(select_menu)

    def get_embed(self, index: int) -> discord.Embed:
        commit = self.commits[index]
        short_sha = commit["sha"][:7]
        author = commit["commit"]["author"]["name"]
        timestamp_str = commit["commit"]["author"]["date"]
        dt = datetime.fromisoformat(timestamp_str.rstrip("Z"))
        formatted_timestamp = f"<t:{int(dt.timestamp())}:F>"
        commit_reason = commit["commit"]["message"]
        
        # Now using self.url for the commit link.
        embed = discord.Embed(
            title=f"Commit {short_sha}",
            color=discord.Color.blurple(),
            description=commit_reason,
            timestamp=datetime.now(timezone.utc)
        )
        # Extract the display name from the commit message
        display_name = commit["commit"]["author"]["name"]

        # Attempt to extract the actual GitHub username; fall back to the display name if not available.
        actual_username = commit.get("author", {}).get("login", display_name)

        embed.add_field(name="Author", value=f"[{display_name}](https://github.com/{actual_username})", inline=True)

        embed.add_field(name="Timestamp", value=formatted_timestamp, inline=True)
        embed.add_field(name="Commit Sha", value=commit['sha'], inline=False)
        embed.add_field(name="Commit Link", value=f"[View Commit]({self.url})", inline=False)
        embed.set_footer(text=f"{self.owner}/{self.repo} - Commit {len(self.commits) - index} of {len(self.commits)}")
        return embed

    async def select_callback(self, interaction: discord.Interaction):
        try:
            selected_index = int(interaction.data["values"][0])
            embed = self.get_embed(selected_index)
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            await interaction.response.send_message(f"Error processing selection: {e}", ephemeral=True)


@bot.tree.command(name="repo_viewer", description="Show a paginated embed with commit details")
async def repo_viewer(interaction: discord.Interaction, repo: str):
    """
    Fetches the 50 most recent commits from the specified repository (using the stored owner or default)
    and displays an interactive embed. The embed shows:
      - Commit ID (short and full SHA)
      - Author
      - Timestamp (as a Discord timestamp)
      - Commit Reason (full commit message)
    Use the select menu (at the bottom) to choose a commit.
    """
    await interaction.response.defer()

    guild_id = str(interaction.guild.id)
    owner_val = owners_data.get(guild_id, default_owner)
    url = f"https://api.github.com/repos/{owner_val}/{repo}/commits?per_page=50"
    response = requests.get(url)
    if response.status_code != 200:
        await interaction.followup.send(f"Error fetching commits for `{owner_val}/{repo}`")
        return

    commits = response.json()
    if not commits:
        await interaction.followup.send(f"No commits found for `{owner_val}/{repo}`")
        return

    view = CommitSelectView(commits, owner_val, repo, url)
    embed = view.get_embed(0)
    await interaction.followup.send(embed=embed, view=view)


# ===============================
# Slash Command: /details
# ===============================
@bot.tree.command(name="details", description="Show details on a repository or a specific commit")
async def details(interaction: discord.Interaction, repo: str, commit: str = None):
    await interaction.response.defer()

    guild_id = str(interaction.guild.id)
    owner_val = owners_data.get(guild_id, default_owner)

    if commit:
        url = f"https://api.github.com/repos/{owner_val}/{repo}/commits/{commit}"
        response = requests.get(url)
        if response.status_code != 200:
            await interaction.followup.send(f"Error fetching commit details for `{commit}` in `{owner_val}/{repo}`")
            return
        data = response.json()
        commit_message = data["commit"]["message"]
        author = data["commit"]["author"]["name"]
        date_str = data["commit"]["author"]["date"]
        dt = datetime.fromisoformat(date_str.rstrip("Z"))
        commit_url = data["html_url"]

        embed = discord.Embed(title="Commit Details", color=discord.Color.green())
        embed.add_field(name="Repository", value=f"{owner_val}/{repo}", inline=False)
        embed.add_field(name="Author", value=author, inline=True)
        embed.add_field(name="Date", value=f"<t:{int(dt.timestamp())}:F>", inline=True)
        embed.add_field(name="Message", value=commit_message, inline=False)
        embed.add_field(name="URL", value=f"[View Commit]({commit_url})", inline=False)
        await interaction.followup.send(embed=embed)
    else:
        url = f"https://api.github.com/repos/{owner_val}/{repo}"
        response = requests.get(url)
        if response.status_code != 200:
            await interaction.followup.send(f"Error fetching repository details for `{owner_val}/{repo}`")
            return
        data = response.json()
        name = data.get("full_name", f"{owner_val}/{repo}")
        description = data.get("description", "No description available.")
        stars = data.get("stargazers_count", 0)
        forks = data.get("forks_count", 0)
        issues = data.get("open_issues_count", 0)
        repo_url = data.get("html_url", "")

        embed = discord.Embed(title=f"Repository Details: {name}", url=repo_url, color=discord.Color.purple())
        embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="Stars", value=str(stars), inline=True)
        embed.add_field(name="Forks", value=str(forks), inline=True)
        embed.add_field(name="Open Issues", value=str(issues), inline=True)
        await interaction.followup.send(embed=embed)

# Run the Flask app in a separate thread
def start_flask():
    app.run(host="0.0.0.0", port=5000)

Thread(target=start_flask).start()

# Run the Discord bot
bot.run(DISCORD_TOKEN)
