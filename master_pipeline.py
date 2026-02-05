import asyncio
import logging
import json
from pathlib import Path
import sys
import concurrent.futures

# Import existing modules
from ai_meme_selector import MemeSelector
from imgur_scraper import RedditMemeScraper
from caption_generator import CaptionGenerator
from discord_bot import DiscordPublisher

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MasterPipeline:
    def __init__(self, config_path="config_final.json"):
        logger.info("Initializing Master Pipeline...")
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.scraper = RedditMemeScraper(config_file="config_no_api.json")
        self.selector = MemeSelector()
        self.caption_gen = CaptionGenerator(config_path)
        self.discord = DiscordPublisher(config_path)
        
        self.ai_config = self.config.get("ai_selector", {})
        self.min_score = self.ai_config.get("min_score_threshold", 0.65)
        self.max_daily = self.ai_config.get("max_daily_selections", 10)
        self.post_interval = self.config.get("discord", {}).get("post_interval_seconds", 300)
        
        # Thread pool for blocking operations
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        
        logger.info("✅ Pipeline initialized successfully")
    
    def _scrape_subreddit_sync(self, subreddit, sort_by, limit):
        """Synchronous scraping (runs in thread)"""
        return self.scraper.scrape_subreddit(subreddit, sort_by=sort_by, limit=limit)
    
    def _score_meme_sync(self, path):
        """Synchronous scoring (runs in thread)"""
        return self.selector.score_meme(path)
    
    async def run_cycle(self):
        """Execute one complete pipeline cycle"""
        logger.info("=" * 60)
        logger.info("Starting pipeline cycle")
        logger.info("=" * 60)
        
        all_content = []
        loop = asyncio.get_event_loop()
        
        try:
            # Step 1: Scrape Reddit (in thread to avoid blocking)
            logger.info("📥 Scraping Reddit...")
            
            subreddits = self.config.get("reddit", {}).get("subreddits", ["memes", "dankmemes"])
            sort_by = self.config.get("reddit", {}).get("sort_by", "hot")
            limit = self.config.get("reddit", {}).get("limit", 50)
            
            for subreddit in subreddits:
                try:
                    # Run scraping in thread pool
                    memes = await loop.run_in_executor(
                        self.executor,
                        self._scrape_subreddit_sync,
                        subreddit, sort_by, limit
                    )
                    
                    if memes:
                        for meme in memes:
                            meme["source"] = "reddit"
                            meme["subreddit"] = subreddit
                            meme["local_path"] = meme["filepath"]
                        all_content.extend(memes)
                        logger.info(f"  r/{subreddit}: {len(memes)} memes")
                except Exception as e:
                    logger.error(f"  r/{subreddit} failed: {e}")
            
            logger.info(f"Total scraped: {len(all_content)} memes")
            
            if not all_content:
                logger.warning("No content scraped. Ending cycle.")
                return
            
            # Step 2: AI scoring (in thread)
            logger.info("🤖 AI scoring content...")
            scored_content = []
            
            for item in all_content:
                try:
                    # Run scoring in thread pool
                    score = await loop.run_in_executor(
                        self.executor,
                        self._score_meme_sync,
                        item["local_path"]
                    )
                    
                    if score >= self.min_score:
                        item["ai_score"] = score
                        scored_content.append(item)
                        logger.info(f"✅ {score:.0%} | {item.get('title', '')[:50]}...")
                        
                except Exception as e:
                    logger.error(f"Scoring error: {e}")
                    continue
            
            # Sort by score, take top N
            scored_content.sort(key=lambda x: x["ai_score"], reverse=True)
            selected = scored_content[:self.max_daily]
            
            logger.info(f"🎯 Selected top {len(selected)} (threshold: {self.min_score:.0%})")
            
            if not selected:
                logger.warning("No content met quality threshold.")
                return
            
            # Step 3: Caption + Discord
            logger.info("📝 Posting to Discord...")
            
            posted = 0
            for item in selected:
                try:
                    caption = self.caption_gen.generate(
                        metadata={
                            "title": item.get("title", ""),
                            "subreddit": item.get("subreddit", ""),
                            "upvotes": item.get("upvotes", 0)
                        },
                        ai_score=item["ai_score"]
                    )
                    
                    success = await self.discord.post_content(
                        file_path=item["local_path"],
                        ai_score=item["ai_score"],
                        caption=caption,
                        metadata={
                            "source": "Reddit",
                            "subreddit": item.get("subreddit", ""),
                            "upvotes": item.get("upvotes", 0)
                        }
                    )
                    
                    if success:
                        posted += 1
                        logger.info(f"✅ Posted {posted}/{len(selected)}")
                        
                        if posted < len(selected):
                            logger.info(f"⏳ Waiting {self.post_interval}s...")
                            await asyncio.sleep(self.post_interval)
                    
                except Exception as e:
                    logger.error(f"Post error: {e}")
                    continue
            
            logger.info(f"🎉 Cycle complete! Posted {posted} items")
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
    
    async def start_bot_and_pipeline(self):
        """Start Discord bot and run pipeline cycles"""
        bot_token = self.config.get("discord", {}).get("bot_token")
        
        if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
            logger.error("❌ Discord bot token not configured!")
            return
        
        async def run_bot():
            await self.discord.bot.start(bot_token)
        
        bot_task = asyncio.create_task(run_bot())
        
        # Wait for bot to be ready
        for i in range(30):
            await asyncio.sleep(1)
            if self.discord.bot.is_ready():
                logger.info("✅ Discord bot connected!")
                break
        else:
            logger.error("Discord bot failed to connect after 30s")
            return
        
        # Run pipeline cycles
        logger.info("Starting pipeline cycles...")
        
        try:
            while True:
                await self.run_cycle()
                
                scrape_interval = self.config.get("reddit", {}).get("scrape_interval_hours", 6)
                logger.info(f"⏳ Waiting {scrape_interval} hours until next cycle...")
                await asyncio.sleep(scrape_interval * 3600)
                
        except KeyboardInterrupt:
            logger.info("Pipeline stopped by user")
        finally:
            self.executor.shutdown(wait=False)
            await self.discord.bot.close()


def main():
    Path("logs").mkdir(exist_ok=True)
    
    pipeline = MasterPipeline()
    
    try:
        asyncio.run(pipeline.start_bot_and_pipeline())
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()