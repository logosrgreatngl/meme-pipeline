import asyncio
import logging
import json
from pathlib import Path
import sys
import concurrent.futures

from ai_meme_selector import MemeSelector
from imgur_scraper import ImgurMemeScraper
from caption_generator import CaptionGenerator
from discord_bot import DiscordPublisher

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
        
        # Use Imgur scraper instead of Reddit
        self.scraper = ImgurMemeScraper()
        self.selector = MemeSelector()
        self.caption_gen = CaptionGenerator(config_path)
        self.discord = DiscordPublisher(config_path)
        
        self.ai_config = self.config.get("ai_selector", {})
        self.min_score = self.ai_config.get("min_score_threshold", 0.65)
        self.max_daily = self.ai_config.get("max_daily_selections", 2)
        self.post_interval = self.config.get("discord", {}).get("post_interval_seconds", 60)
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        
        logger.info("✅ Pipeline initialized successfully")
    
    def _scrape_sync(self, limit):
        return self.scraper.scrape_subreddit(limit=limit)
    
    def _score_meme_sync(self, path):
        return self.selector.score_meme(path)
    
    async def run_cycle(self):
        logger.info("=" * 60)
        logger.info("Starting pipeline cycle")
        logger.info("=" * 60)
        
        all_content = []
        loop = asyncio.get_event_loop()
        
        try:
            logger.info("📥 Scraping Imgur...")
            
            limit = self.config.get("reddit", {}).get("limit", 30)
            
            memes = await loop.run_in_executor(
                self.executor,
                self._scrape_sync,
                limit
            )
            
            if memes:
                for meme in memes:
                    meme["source"] = "imgur"
                    meme["subreddit"] = "imgur"
                    meme["local_path"] = meme["filepath"]
                all_content.extend(memes)
            
            logger.info(f"Total scraped: {len(all_content)} memes")
            
            if not all_content:
                logger.warning("No content scraped. Ending cycle.")
                return
            
            logger.info("🤖 AI scoring content...")
            scored_content = []
            
            for item in all_content:
                try:
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
            
            scored_content.sort(key=lambda x: x["ai_score"], reverse=True)
            selected = scored_content[:self.max_daily]
            
            logger.info(f"🎯 Selected top {len(selected)} (threshold: {self.min_score:.0%})")
            
            if not selected:
                logger.warning("No content met quality threshold.")
                return
            
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
                            "source": "Imgur",
                            "subreddit": item.get("subreddit", ""),
                            "upvotes": item.get("upvotes", 0)
                        }
                    )
                    
                    if success:
                        posted += 1
                        logger.info(f"✅ Posted {posted}/{len(selected)}")
                        
                        if posted < len(selected):
                            await asyncio.sleep(self.post_interval)
                    
                except Exception as e:
                    logger.error(f"Post error: {e}")
                    continue
            
            logger.info(f"🎉 Cycle complete! Posted {posted} items")
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)


def main():
    Path("logs").mkdir(exist_ok=True)
    
    pipeline = MasterPipeline()
    
    try:
        asyncio.run(pipeline.run_cycle())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
