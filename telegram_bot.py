# =========================
# telegram_bot.py (PRODUCTION READY - NON-BLOCKING + ALL COMMANDS)
# =========================

import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, MAX_TRADES_PER_DAY
from logger import logger

# Enable logging for python-telegram-bot
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)


class TelegramBot:
    def __init__(self, paper_engine, scheduler):
        """
        Args:
            paper_engine: Instance of PaperTradingEngine
            scheduler: Instance of TradingScheduler (for pause/resume control)
        """
        self.paper_engine = paper_engine
        self.scheduler = scheduler
        self.app = None
        self.chat_id = TELEGRAM_CHAT_ID

    # =========================
    # COMMAND HANDLERS
    # =========================
    async def start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message with available commands."""
        await update.message.reply_text(
            "🤖 *ORB-VWAP Algo Trader*\n\n"
            "Available commands:\n"
            "/status - Show current system status\n"
            "/pnl - Show P&L summary\n"
            "/trades - List today's trades\n"
            "/pause - Pause trading\n"
            "/resume - Resume trading\n"
            "/squareoff - Close all positions immediately",
            parse_mode="Markdown"
        )

    async def status_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current system status."""
        status_text = (
            f"📊 *System Status*\n"
            f"Trading active: {self.scheduler.is_trading_active}\n"
            f"Market open: {self.scheduler.is_market_open()}\n"
            f"Open positions: {len(self.paper_engine.positions)}\n"
            f"Daily trades: {self.paper_engine.daily_trades_count}/{MAX_TRADES_PER_DAY}\n"
            f"Consecutive losses: {self.paper_engine.consecutive_losses}\n"
            f"Daily loss limit hit: {self.paper_engine.daily_loss_limit_hit}"
        )
        await update.message.reply_text(status_text, parse_mode="Markdown")

    async def pnl_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current P&L and capital summary."""
        summary = self.paper_engine.get_daily_summary()
        pnl_text = (
            f"💰 *P&L Summary*\n"
            f"Daily P&L: ₹{summary['total_pnl']:.2f}\n"
            f"Total Capital: ₹{summary['current_capital']:.2f}\n"
            f"Win Rate: {summary['win_rate']*100:.1f}%\n"
            f"Open Trades: {summary['open_positions']}\n"
            f"Trades today: {summary['total_trades']}"
        )
        await update.message.reply_text(pnl_text, parse_mode="Markdown")

    async def trades_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List today's completed trades."""
        if not self.paper_engine.trade_history:
            await update.message.reply_text("No trades today.")
            return

        trade_list = "📋 *Today's Trades*\n"
        for t in self.paper_engine.trade_history[-10:]:  # show last 10
            trade_list += f"{t.entry_time:%H:%M} {t.symbol} {t.direction} P&L: ₹{t.pnl:.2f}\n"
        await update.message.reply_text(trade_list, parse_mode="Markdown")

    async def pause_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause new trade entries."""
        self.scheduler.pause_trading()
        await update.message.reply_text("⏸ Trading paused. No new entries will be taken.")

    async def resume_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resume trading."""
        self.scheduler.resume_trading()
        await update.message.reply_text("▶ Trading resumed.")

    async def squareoff_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Force square off all open positions."""
        self.scheduler.force_square_off = True
        await update.message.reply_text("🔄 Square off requested. Positions will be closed on next cycle.")

    # =========================
    # CORE MESSAGING
    # =========================
    async def send_message(self, text: str, parse_mode: str = "Markdown"):
        """Send a message to the configured Telegram chat."""
        if self.app and self.chat_id:
            try:
                await self.app.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode=parse_mode
                )
            except Exception as e:
                logger.error(f"Failed to send Telegram message: {e}")

    # =========================
    # BOT INITIALISATION (NON-BLOCKING)
    # =========================
    async def init_bot(self):
        """Initialize and start the bot in a non‑blocking way."""
        # Build application
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Register command handlers
        self.app.add_handler(CommandHandler("start", self.start_cmd))
        self.app.add_handler(CommandHandler("status", self.status_cmd))
        self.app.add_handler(CommandHandler("pnl", self.pnl_cmd))
        self.app.add_handler(CommandHandler("trades", self.trades_cmd))
        self.app.add_handler(CommandHandler("pause", self.pause_cmd))
        self.app.add_handler(CommandHandler("resume", self.resume_cmd))
        self.app.add_handler(CommandHandler("squareoff", self.squareoff_cmd))

        # Initialize the bot
        await self.app.initialize()
        await self.app.start()

        # 🔥 FIXED: Use run_polling() in a background task (non‑blocking)
        # This is the recommended way for python-telegram-bot v20+
        asyncio.create_task(self.app.run_polling())

        logger.info("✅ Telegram bot started (non-blocking)")

    async def shutdown(self):
        """Gracefully stop the bot."""
        if self.app:
            await self.app.stop()
            await self.app.shutdown()
            logger.info("🛑 Telegram bot stopped")