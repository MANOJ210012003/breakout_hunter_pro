# =========================
# FINAL PRODUCTION-READY strategy.py
# =========================

import pandas as pd
from datetime import datetime
from typing import Optional, Tuple

from config import *
from indicators import (
    calculate_vwap,
    calculate_rsi,
    calculate_volume_sma,
    is_rsi_rising,
    is_rsi_falling,
)


class ORBVWAPStrategy:
    def __init__(self, symbol: str, df: pd.DataFrame, nifty_df: pd.DataFrame = None):
        self.symbol = symbol
        self.df = df.copy() if not df.empty else pd.DataFrame()
        self.nifty_df = nifty_df.copy() if nifty_df is not None else pd.DataFrame()

        self.orb_high: Optional[float] = None
        self.orb_low: Optional[float] = None

    # =========================
    # ORB CALCULATION
    # =========================
    def calculate_orb(self) -> Tuple[Optional[float], Optional[float]]:
        if self.df.empty:
            return None, None

        orb_df = self.df.between_time(ORB_START, ORB_END)
        if orb_df.empty:
            return None, None

        self.orb_high = orb_df["high"].max()
        self.orb_low = orb_df["low"].min()

        return self.orb_high, self.orb_low

    # =========================
    # INDICATORS
    # =========================
    def calculate_indicators(self):
        if self.df.empty:
            return

        self.df["vwap"] = calculate_vwap(self.df)
        self.df["rsi"] = calculate_rsi(self.df, RSI_PERIOD)
        self.df["volume_sma"] = calculate_volume_sma(self.df, VOLUME_PERIOD)

    # =========================
    # TIME FILTER
    # =========================
    def is_trading_time(self) -> bool:
        now = datetime.now().time()

        morning = (
            datetime.strptime(MORNING_SESSION_START, "%H:%M").time()
            <= now
            <= datetime.strptime(MORNING_SESSION_END, "%H:%M").time()
        )

        afternoon = (
            datetime.strptime(AFTERNOON_SESSION_START, "%H:%M").time()
            <= now
            <= datetime.strptime(AFTERNOON_SESSION_END, "%H:%M").time()
        )

        return morning or afternoon

    # =========================
    # BREAKOUT
    # =========================
    def check_breakout(self) -> Tuple[Optional[str], Optional[float]]:
        if self.df.empty or self.orb_high is None:
            return None, None

        price = self.df["close"].iloc[-1]

        if price > self.orb_high:
            return "LONG", self.orb_high
        elif price < self.orb_low:
            return "SHORT", self.orb_low

        return None, None

    # =========================
    # VWAP
    # =========================
    def check_vwap(self, direction: str) -> bool:
        if "vwap" not in self.df.columns:
            return False

        price = self.df["close"].iloc[-1]
        vwap = self.df["vwap"].iloc[-1]

        return (direction == "LONG" and price > vwap) or (
            direction == "SHORT" and price < vwap
        )

    # =========================
    # RSI
    # =========================
    def check_rsi(self, direction: str) -> bool:
        if "rsi" not in self.df.columns:
            return False

        rsi_series = self.df["rsi"]
        last = rsi_series.iloc[-1]

        if direction == "LONG":
            return last > RSI_LONG_THRESHOLD and is_rsi_rising(rsi_series)

        return last < RSI_SHORT_THRESHOLD and is_rsi_falling(rsi_series)

    # =========================
    # VOLUME (FIXED)
    # =========================
    def check_volume(self) -> bool:
        if self.df.empty or "volume_sma" not in self.df.columns:
            return False

        last_volume = self.df["volume"].iloc[-1]
        last_sma = self.df["volume_sma"].iloc[-1]

        condition = last_volume > VOLUME_MULTIPLIER * last_sma

        if VOLUME_INCREASE_REQUIRED and len(self.df) > 1:
            prev_volume = self.df["volume"].iloc[-2]
            condition = condition and last_volume > prev_volume

        return condition

    # =========================
    # RETEST (STRONG)
    # =========================
    def check_retest(self, direction: str, level: float) -> bool:
        if self.df.empty or len(self.df) < 2:
            return False

        last = self.df["close"].iloc[-1]
        prev = self.df["close"].iloc[-2]
        tolerance = level * RETEST_TOLERANCE

        if direction == "LONG":
            return (
                prev > level
                and last > level
                and abs(last - level) <= tolerance
            )

        return (
            prev < level
            and last < level
            and abs(last - level) <= tolerance
        )

    # =========================
    # RELATIVE STRENGTH
    # =========================
    def check_relative_strength(self, direction: str) -> bool:
        if self.df.empty:
            return False

        # fallback if nifty missing
        if self.nifty_df.empty:
            return True

        stock_return = (
            self.df["close"].iloc[-1] / self.df["close"].iloc[0] - 1
        )
        nifty_return = (
            self.nifty_df["close"].iloc[-1]
            / self.nifty_df["close"].iloc[0]
            - 1
        )

        if direction == "LONG":
            return stock_return - nifty_return > RELATIVE_STRENGTH_DELTA

        return nifty_return - stock_return > RELATIVE_STRENGTH_DELTA

    # =========================
    # FINAL EVALUATION
    # =========================
    def evaluate(self) -> Tuple[bool, Optional[str], Optional[float]]:
        if not self.is_trading_time():
            return False, None, None

        if self.df.empty:
            return False, None, None

        # indicators + orb
        self.calculate_indicators()
        self.calculate_orb()

        direction, level = self.check_breakout()
        if not direction:
            return False, None, None

        # all filters
        conditions = [
            self.check_vwap(direction),
            self.check_rsi(direction),
            self.check_volume(),
            self.check_retest(direction, level),
            self.check_relative_strength(direction),
        ]

        if not all(conditions):
            return False, None, None

        return True, direction, level
