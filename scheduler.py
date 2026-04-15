# =========================
# scheduler.py (CLEAN + PRODUCTION READY)
# =========================

import asyncio
import pytz
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import *
from logger import logger
from dhan_client import DhanClient
from strategy import ORBVWAPStrategy

class TradingScheduler:
    def __init__(self, paper_engine, telegram_bot):
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone("Asia/Kolkata"))
        self.paper_engine = paper_engine
        self.telegram_bot = telegram_bot
        self.client = DhanClient()

        # Cooldown tracking (5 minutes per symbol)
        self.last_trade_time = {}

        # Stock universe (high liquidity Nifty 50)
        self.stocks = [
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
            "ITC", "LT", "SBIN", "AXISBANK", "BAJFINANCE",
            "MARUTI", "SUNPHARMA", "TITAN", "ONGC", "NTPC",
            "POWERGRID", "ULTRACEMCO", "HINDUNILVR", "KOTAKBANK", "BHARTIARTL"
        ]

        # Flag for user-requested square off
        self.force_square_off = False
        self.is_trading_active = True

    # =========================
    # MARKET TIME CHECK
    # =========================
    def is_market_open(self) -> bool:
        now = datetime.now(pytz.timezone("Asia/Kolkata")).time()
        market_start = time(9, 15)
        market_end = time(15, 30)
        return market_start <= now <= market_end

    def pause_trading(self):
        self.is_trading_active = False
        logger.info("Trading paused by user")

    def resume_trading(self):
        self.is_trading_active = True
        logger.info("Trading resumed by user")

    # =========================
    # MAIN STRATEGY LOOP
    # =========================
    async def run_cycle(self):
        """Executed every 2 minutes during market hours."""
        try:
            if not self.is_market_open():
                return

            if not self.is_trading_active:
                return

            now = datetime.now(pytz.timezone("Asia/Kolkata"))

            # Fetch Nifty for Relative Strength
            nifty_df = self.client.fetch_nifty_5min()

            current_prices = {}

            # =========================
            # EXIT CHECK (Stop Loss / Targets)
            # =========================
            for symbol in list(self.paper_engine.positions.keys()):
                df = self.client.fetch_intraday_5min(symbol, days=1)
                if not df.empty:
                    current_prices[symbol] = df['close'].iloc[-1]

            self.paper_engine.check_exits(current_prices)

            # =========================
            # SQUARE OFF CHECK (Time or User Requested)
            # =========================
            square_off_time = datetime.strptime(SQUARE_OFF_TIME, "%H:%M").time()
            if self.force_square_off or now.time() >= square_off_time:
                if current_prices:
                    self.paper_engine.square_off_all(current_prices)
                    await self.telegram_bot.send_message("🔴 All positions squared off.")
                self.force_square_off = False
                return

            # =========================
            # ENTRY CHECK (New Signals)
            # =========================
            if not self.paper_engine.can_trade():
                return

            for symbol in self.stocks:
                # Skip if already in position
                if symbol in self.paper_engine.positions:
                    continue

                # Cooldown: 5 minutes per symbol
                if symbol in self.last_trade_time:
                    diff_seconds = (datetime.now() - self.last_trade_time[symbol]).total_seconds()
                    if diff_seconds < 300:
                        continue

                df = self.client.fetch_intraday_5min(symbol, days=2)
                if df.empty or len(df) < 30:
                    continue

                strategy = ORBVWAPStrategy(symbol, df, nifty_df)
                signal, direction, orb_level = strategy.evaluate()

                if not signal:
                    continue

                entry_price = df['close'].iloc[-1]
                trade = self.paper_engine.open_trade(symbol, direction, entry_price, orb_level)

                if trade:
                    self.last_trade_time[symbol] = datetime.now()

                    msg = (
                        f"🟢 *NEW TRADE*\n"
                        f"Symbol: {symbol}\n"
                        f"Direction: {direction}\n"
                        f"Entry: {trade.entry_price:.2f}\n"
                        f"SL: {trade.stop_loss:.2f}\n"
                        f"T1: {trade.target_1:.2f}\n"
                        f"T2: {trade.target_2:.2f}\n"
                        f"Qty: {trade.quantity}\n"
                        f"Risk: ₹{trade.risk_amount:.2f}"
                    )
                    await self.telegram_bot.send_message(msg)

        except Exception as e:
            logger.error(f"❌ Scheduler Error: {e}", exc_info=True)

    # =========================
    # DAILY SUMMARY
    # =========================
    async def send_daily_summary(self):
        """Send end-of-day performance summary."""
        try:
            summary = self.paper_engine.get_daily_summary()

            msg = (
                f"📊 *DAILY SUMMARY*\n"
                f"Trades: {summary['total_trades']}\n"
                f"Win Rate: {summary['win_rate']*100:.1f}%\n"
                f"P&L: ₹{summary['total_pnl']:.2f}\n"
                f"Capital: ₹{summary['current_capital']:.2f}\n"
                f"Loss Limit Hit: {summary['loss_limit_hit']}"
            )
            await self.telegram_bot.send_message(msg)

            # Reset daily counters for next day
            self.paper_engine.reset_daily()

        except Exception as e:
            logger.error(f"❌ Summary Error: {e}", exc_info=True)

    # =========================
    # START SCHEDULER
    # =========================
    def start(self):
        # Run strategy cycle every 2 minutes during market hours
        self.scheduler.add_job(
            self.run_cycle,
            CronTrigger(minute="*/2", timezone=pytz.timezone("Asia/Kolkata")),
            id="strategy_cycle"
        )

        # Daily summary at 15:30 IST
        self.scheduler.add_job(
            self.send_daily_summary,
            CronTrigger(hour=15, minute=30, timezone=pytz.timezone("Asia/Kolkata")),
            id="daily_summary"
        )

        self.scheduler.start()
        logger.info("✅ Scheduler started (non-blocking)")

    # =========================
    # STOP SCHEDULER
    # =========================
    def stop(self):
        self.scheduler.shutdown()
        logger.info("🛑 Scheduler stopped")