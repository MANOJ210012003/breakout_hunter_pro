import asyncio
import signal
from logger import logger
from paper_trade import PaperTradingEngine
from telegram_bot import TelegramBot
from scheduler import TradingScheduler

async def main():
    # Initialize components
    paper_engine = PaperTradingEngine()
    scheduler = TradingScheduler(paper_engine, None)
    telegram_bot = TelegramBot(paper_engine, scheduler)
    scheduler.telegram_bot = telegram_bot

    # ✅ FIXED: Use init_bot() instead of run()
    await telegram_bot.init_bot()

    # Start scheduler
    scheduler.start()

    # Send startup message
    await telegram_bot.send_message("🚀 ORB-VWAP Algo Trader started. Type /start for commands.")

    # Graceful shutdown
    stop_event = asyncio.Event()
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        stop_event.set()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await stop_event.wait()

    # Cleanup
    scheduler.stop()
    await telegram_bot.shutdown()
    logger.info("Application shut down cleanly.")

if __name__ == "__main__":
    asyncio.run(main())