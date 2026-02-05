import asyncio
import logging
import os
import shutil
from pathlib import Path
from master_pipeline import MasterPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_files():
    """Delete downloaded files after pipeline completes"""
    folders_to_clean = ['memes', 'tiktok_downloads']
    
    for folder in folders_to_clean:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                os.makedirs(folder, exist_ok=True)
                logger.info(f"🧹 Cleaned up {folder}/")
            except Exception as e:
                logger.error(f"Cleanup error for {folder}: {e}")

async def run_once():
    Path("logs").mkdir(exist_ok=True)
    Path("memes").mkdir(exist_ok=True)
    
    pipeline = MasterPipeline()
    bot_token = pipeline.config.get("discord", {}).get("bot_token")
    
    async def run_bot():
        await pipeline.discord.bot.start(bot_token)
    
    bot_task = asyncio.create_task(run_bot())
    
    for i in range(30):
        await asyncio.sleep(1)
        if pipeline.discord.bot.is_ready():
            logger.info("✅ Bot connected!")
            break
    else:
        logger.error("Bot failed to connect")
        return
    
    try:
        await pipeline.run_cycle()
    finally:
        await pipeline.discord.bot.close()
        cleanup_files()
        logger.info("✅ Done!")

if __name__ == "__main__":
    asyncio.run(run_once())