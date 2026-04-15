import pandas as pd
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from config import *
from logger import logger

@dataclass
class Trade:
    symbol: str
    direction: str
    entry_time: datetime
    entry_price: float          # actual executed price (with slippage)
    orb_level: float
    stop_loss: float
    target_1: float
    target_2: float
    quantity: int
    risk_amount: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    exit_reason: str = ""
    target_1_hit: bool = False
    target_2_hit: bool = False
    sl_hit: bool = False
    partial_qty_exited: Dict[str, int] = None

class PaperTradingEngine:
    def __init__(self):
        self.capital = INITIAL_CAPITAL
        self.initial_capital = INITIAL_CAPITAL
        self.positions: Dict[str, Trade] = {}
        self.trade_history: List[Trade] = []
        self.daily_trades_count = 0
        self.daily_pnl = 0.0
        self.daily_loss_limit_hit = False
        self.consecutive_losses = 0
        self.max_trades_hit = False

        if not os.path.exists(TRADE_LOG_FILE):
            with open(TRADE_LOG_FILE, "w") as f:
                f.write("timestamp,symbol,direction,entry_price,exit_price,quantity,pnl,exit_reason\n")

    def can_trade(self) -> bool:
        if self.daily_trades_count >= MAX_TRADES_PER_DAY:
            self.max_trades_hit = True
            return False
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            return False
        if self.daily_loss_limit_hit:
            return False
        return True

    def calculate_position_size(self, entry_price: float, stop_loss: float) -> int:
        risk_amount = self.capital * RISK_PER_TRADE
        price_risk = abs(entry_price - stop_loss)
        if price_risk <= 0:
            return 0
        quantity = int(risk_amount / price_risk)
        return max(1, quantity)

    def open_trade(self, symbol: str, direction: str, entry_price: float, orb_level: float):
        if not self.can_trade():
            return None
        if symbol in self.positions:
            return None

        # 🔥 Apply slippage: entry worse by SLIPPAGE
        if direction == "LONG":
            entry_price_exec = entry_price * (1 + SLIPPAGE)
            stop_loss = orb_level
            target_1 = entry_price_exec + (entry_price_exec - stop_loss) * TARGET_1_R
            target_2 = entry_price_exec + (entry_price_exec - stop_loss) * TARGET_2_R
        else:
            entry_price_exec = entry_price * (1 - SLIPPAGE)
            stop_loss = orb_level
            target_1 = entry_price_exec - (stop_loss - entry_price_exec) * TARGET_1_R
            target_2 = entry_price_exec - (stop_loss - entry_price_exec) * TARGET_2_R

        quantity = self.calculate_position_size(entry_price_exec, stop_loss)
        risk_amount = abs(entry_price_exec - stop_loss) * quantity

        trade = Trade(
            symbol=symbol,
            direction=direction,
            entry_time=datetime.now(),
            entry_price=entry_price_exec,
            orb_level=orb_level,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            quantity=quantity,
            risk_amount=risk_amount,
            partial_qty_exited={"target_1": 0, "target_2": 0, "trailing": 0}
        )
        self.positions[symbol] = trade
        self.daily_trades_count += 1
        logger.info(f"Opened {direction} trade for {symbol} at {entry_price_exec:.2f} (slippage applied), qty={quantity}, SL={stop_loss:.2f}")
        return trade

    def close_trade(self, symbol: str, exit_price: float, exit_reason: str):
        if symbol not in self.positions:
            return
        trade = self.positions.pop(symbol)
        trade.exit_time = datetime.now()
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason

        # Calculate P&L considering partial exits already booked
        if trade.direction == "LONG":
            pnl_remaining = (exit_price - trade.entry_price) * trade.quantity
        else:
            pnl_remaining = (trade.entry_price - exit_price) * trade.quantity

        booked_pnl = 0
        if trade.target_1_hit:
            booked_pnl += (trade.target_1 - trade.entry_price) * trade.partial_qty_exited["target_1"] * (1 if trade.direction=="LONG" else -1)
        if trade.target_2_hit:
            booked_pnl += (trade.target_2 - trade.entry_price) * trade.partial_qty_exited["target_2"] * (1 if trade.direction=="LONG" else -1)

        total_pnl = pnl_remaining + booked_pnl
        trade.pnl = total_pnl

        self.capital += total_pnl
        self.daily_pnl += total_pnl
        self.trade_history.append(trade)

        if total_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        if self.daily_pnl <= -self.initial_capital * DAILY_LOSS_LIMIT:
            self.daily_loss_limit_hit = True

        self._log_trade_to_csv(trade)
        logger.info(f"Closed {symbol} at {exit_price:.2f}, P&L: {total_pnl:.2f}, reason: {exit_reason}")
        return trade

    def check_exits(self, current_prices: Dict[str, float]):
        for symbol, trade in list(self.positions.items()):
            price = current_prices.get(symbol)
            if price is None:
                continue

            # Stop loss
            if (trade.direction == "LONG" and price <= trade.stop_loss) or \
               (trade.direction == "SHORT" and price >= trade.stop_loss):
                self.close_trade(symbol, price, "Stop Loss")
                continue

            # Target 1
            if not trade.target_1_hit:
                if (trade.direction == "LONG" and price >= trade.target_1) or \
                   (trade.direction == "SHORT" and price <= trade.target_1):
                    exit_qty = int(trade.quantity * 0.5)
                    if exit_qty > 0:
                        trade.quantity -= exit_qty
                        trade.partial_qty_exited["target_1"] = exit_qty
                        trade.target_1_hit = True
                        # Book profit
                        if trade.direction == "LONG":
                            self.capital += (trade.target_1 - trade.entry_price) * exit_qty
                        else:
                            self.capital += (trade.entry_price - trade.target_1) * exit_qty
                        logger.info(f"Target 1 hit for {symbol}, exited {exit_qty} shares")

            # Target 2
            if trade.target_1_hit and not trade.target_2_hit:
                if (trade.direction == "LONG" and price >= trade.target_2) or \
                   (trade.direction == "SHORT" and price <= trade.target_2):
                    exit_qty = int(trade.quantity * 0.3)
                    if exit_qty > 0:
                        trade.quantity -= exit_qty
                        trade.partial_qty_exited["target_2"] = exit_qty
                        trade.target_2_hit = True
                        if trade.direction == "LONG":
                            self.capital += (trade.target_2 - trade.entry_price) * exit_qty
                        else:
                            self.capital += (trade.entry_price - trade.target_2) * exit_qty
                        logger.info(f"Target 2 hit for {symbol}, exited {exit_qty} shares")

    def square_off_all(self, current_prices: Dict[str, float]):
        for symbol in list(self.positions.keys()):
            price = current_prices.get(symbol)
            if price:
                self.close_trade(symbol, price, "Square Off")

    def _log_trade_to_csv(self, trade: Trade):
        with open(TRADE_LOG_FILE, "a") as f:
            f.write(f"{trade.entry_time},{trade.symbol},{trade.direction},{trade.entry_price},"
                    f"{trade.exit_price},{trade.quantity},{trade.pnl:.2f},{trade.exit_reason}\n")

    def get_daily_summary(self) -> Dict:
        winning_trades = [t for t in self.trade_history if t.pnl > 0]
        win_rate = len(winning_trades) / len(self.trade_history) if self.trade_history else 0
        return {
            "total_trades": len(self.trade_history),
            "win_rate": win_rate,
            "total_pnl": self.daily_pnl,
            "current_capital": self.capital,
            "open_positions": len(self.positions),
            "max_trades_hit": self.max_trades_hit,
            "loss_limit_hit": self.daily_loss_limit_hit
        }

    def reset_daily(self):
        self.daily_trades_count = 0
        self.daily_pnl = 0.0
        self.daily_loss_limit_hit = False
        self.consecutive_losses = 0
        self.max_trades_hit = False