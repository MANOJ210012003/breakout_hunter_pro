import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
from dhanhq import dhanhq
from config import DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN, NIFTY_SYMBOL
from logger import logger

class DhanClient:
    def __init__(self):
        self.client = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        self.segment = "NSE"
        self.exchange = "NSE"
        self._security_ids = {}
        self._data_cache = {}          # 🔥 ADDED: simple cache to reduce API calls

    def get_security_id(self, symbol: str) -> Optional[str]:
        if symbol in self._security_ids:
            return self._security_ids[symbol]
        try:
            instruments = self.client.get_instruments()
            for inst in instruments.get("data", []):
                if inst["symbol"] == symbol and inst["segment"] == self.segment:
                    self._security_ids[symbol] = inst["security_id"]
                    return inst["security_id"]
            logger.warning(f"Security ID not found for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Error fetching security ID for {symbol}: {e}")
            return None

    def fetch_intraday_5min(self, symbol: str, days: int = 5) -> pd.DataFrame:
        """Fetch 5‑minute OHLCV data with caching."""
        cache_key = f"{symbol}_{days}"
        if cache_key in self._data_cache:
            # Return cached data if fresh (< 1 min old)
            df, timestamp = self._data_cache[cache_key]
            if (datetime.now() - timestamp).seconds < 60:
                return df.copy()

        sec_id = self.get_security_id(symbol)
        if not sec_id:
            return pd.DataFrame()

        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            response = self.client.intraday_minute_data(
                security_id=sec_id,
                exchange_segment=self.segment,
                from_date=start_date.strftime("%Y-%m-%d"),
                to_date=end_date.strftime("%Y-%m-%d"),
                interval="5"
            )
            data = response.get("data", [])
            if not data:
                logger.warning(f"No intraday data for {symbol}")
                return pd.DataFrame()

            df = pd.DataFrame(data)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)
            df.rename(columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume"
            }, inplace=True)

            self._data_cache[cache_key] = (df.copy(), datetime.now())
            return df
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_nifty_5min(self) -> pd.DataFrame:
        """Fetch Nifty 5‑minute data using correct symbol."""
        return self.fetch_intraday_5min(NIFTY_SYMBOL)