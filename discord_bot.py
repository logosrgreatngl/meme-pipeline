import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DiscordPublisher:
    """Handles posting AI-selected content to Discord"""
    
    def __init__(self, config_path="config_final.json"):
        self.config = self._load_config(config_path)
        self.discord_config = self.config.get("discord", {})
        self.history_file = self.config.get("history", {}).get("discord_posted", "discord_posted_history.json")
        self.posted_history = self._load_history()
        
        # Bot setup
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        
        self._setup_events()
    
    def _load_config(self, config_path):
        """Load configuration file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config: {e}")
            raise
    
    def _load_history(self):
        """Load posting history to avoid duplicates"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Corrupted history file, creating new one")
                return {"posted": []}
        return {"posted": []}
    
    def _save_history(self):
        """Save posting history"""
        max_entries = self.config.get("history", {}).get("max_history_entries", 1000)
        
        # Trim history if too large
        if len(self.posted_history["posted"]) > max_entries:
            self.posted_history["posted"] = self.posted_history["posted"][-max_entries:]
        
        with open(self.history_file, 'w') as f:
            json.dump(self.posted_history, f, indent=2)
    
    def _setup_events(self):
        """Setup bot event handlers"""
        
        @self.bot.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.bot.user}")
            print(f"✅ Discord Bot Ready: {self.bot.user}")
        
        @self.bot.event
        async def on_message(message):
            if message.author == self.bot.user:
                return
            await self.bot.process_commands(message)
    
    def is_already_posted(self, content_id):
        """Check if content was already posted"""
        return content_id in [entry["content_id"] for entry in self.posted_history["posted"]]
    
    async def post_content(self, 
                          file_path, 
                          ai_score, 
                          caption, 
                          metadata=None):
        """
        Post content to Discord channel
        
        Args:
            file_path: Path to meme/video file
            ai_score: AI quality score (0-1)
            caption: Generated caption with hashtags
            metadata: Optional dict with source, upvotes, etc.
        """
        try:
            channel_id = int(self.discord_config["channel_id"])
            channel = self.bot.get_channel(channel_id)
            
            if not channel:
                logger.error(f"Channel {channel_id} not found")
                return False
            
            # Check if already posted
            content_id = self._generate_content_id(file_path)
            if self.is_already_posted(content_id):
                logger.info(f"Content already posted: {content_id}")
                return False
            
            # Build embed message
            embed = discord.Embed(
                title="🎯 AI-Selected Content",
                description=caption,
                color=self._score_to_color(ai_score),
                timestamp=datetime.utcnow()
            )
            
            # Add metadata fields
            embed.add_field(name="AI Score", value=f"{ai_score:.2%} ⭐", inline=True)
            
            if metadata:
                if "source" in metadata:
                    embed.add_field(name="Source", value=metadata["source"], inline=True)
                if "upvotes" in metadata:
                    embed.add_field(name="Upvotes", value=f"⬆️ {metadata['upvotes']:,}", inline=True)
                if "subreddit" in metadata:
                    embed.add_field(name="Subreddit", value=f"r/{metadata['subreddit']}", inline=True)
            
            embed.set_footer(text="AI Content Pipeline v2.0")
            
            # Send file + embed
            file = discord.File(file_path)
            message = await channel.send(file=file, embed=embed)
            
            # Add reactions if enabled
            if self.discord_config.get("enable_reactions", True):
                await message.add_reaction("👍")
                await message.add_reaction("👎")
                await message.add_reaction("🔥")
            
            # Record in history
            self._record_post(content_id, file_path, ai_score, metadata)
            
            logger.info(f"✅ Posted to Discord: {file_path}")
            return True
            
        except discord.Forbidden:
            logger.error("Bot lacks permissions to post in channel")
            return False
        except discord.HTTPException as e:
            logger.error(f"Discord API error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error posting to Discord: {e}")
            return False
    
    def _generate_content_id(self, file_path):
        """Generate unique ID for content"""
        from hashlib import md5
        filename = Path(file_path).name
        return md5(filename.encode()).hexdigest()[:16]
    
    def _score_to_color(self, score):
        """Convert AI score to Discord embed color"""
        if score >= 0.8:
            return discord.Color.gold()
        elif score >= 0.65:
            return discord.Color.green()
        else:
            return discord.Color.blue()
    
    def _record_post(self, content_id, file_path, ai_score, metadata):
        """Record successful post in history"""
        entry = {
            "content_id": content_id,
            "file_path": file_path,
            "ai_score": ai_score,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.posted_history["posted"].append(entry)
        self._save_history()
    
    def run(self, token=None):
        """Start the Discord bot"""
        token = token or self.discord_config.get("bot_token")
        if not token or token == "YOUR_BOT_TOKEN_HERE":
            raise ValueError("Discord bot token not configured in config_final.json")
        
        self.bot.run(token)


# Standalone async function for pipeline integration
async def send_to_discord(publisher, file_path, ai_score, caption, metadata=None):
    """Helper function to post from pipeline without blocking"""
    return await publisher.post_content(file_path, ai_score, caption, metadata)


if __name__ == "__main__":
    # Test mode
    logging.basicConfig(level=logging.INFO)
    publisher = DiscordPublisher()
    publisher.run()