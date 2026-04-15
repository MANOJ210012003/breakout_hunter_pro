import numpy as np
import pandas as pd

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculate rolling VWAP from OHLCV data."""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    return vwap

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate RSI indicator."""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_volume_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Simple moving average of volume."""
    return df['volume'].rolling(window=period).mean()

def is_rsi_rising(rsi_series: pd.Series, lookback: int = 3) -> bool:
    """Check if RSI has been rising over the last `lookback` periods."""
    if len(rsi_series) < lookback + 1:
        return False
    recent = rsi_series.iloc[-lookback:]
    return all(recent.diff().dropna() > 0)

def is_rsi_falling(rsi_series: pd.Series, lookback: int = 3) -> bool:
    """Check if RSI has been falling over the last `lookback` periods."""
    if len(rsi_series) < lookback + 1:
        return False
    recent = rsi_series.iloc[-lookback:]
    return all(recent.diff().dropna() < 0)