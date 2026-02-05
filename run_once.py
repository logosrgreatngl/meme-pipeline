import asyncio
import logging
from pathlib import Path
from master_pipeline import MasterPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    await pipeline.run_cycle()
    await pipeline.discord.bot.close()
    logger.info("✅ Done!")

if __name__ == "__main__":
    asyncio.run(run_once())
