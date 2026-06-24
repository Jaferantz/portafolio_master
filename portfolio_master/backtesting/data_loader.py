"""
Data loader for backtesting: loads historical price data from various sources.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from portfolio_master.utils.binance_api import fetch_klines as binance_fetch_klines
import json
import urllib.request
import urllib.parse

def load_from_binance(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 1000) -> pd.DataFrame:
    """
    Load historical klines from Binance and return a DataFrame.
    """
    try:
        query = urllib.parse.urlencode({
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        })
        url  = f"https://api.binance.com/api/v3/klines?{query}"
        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
        df = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        # Convert to numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df[['open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        print(f"Error loading from Binance: {e}")
        return None

def load_from_csv(file_path: str or Path) -> pd.DataFrame:
    """
    Load historical data from a CSV file.
    Expected columns: timestamp, open, high, low, close, volume
    """
    try:
        df = pd.read_csv(file_path, parse_dates=['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        print(f"Error loading from CSV: {e}")
        return None

def load_data(source: str = "binance", **kwargs) -> pd.DataFrame:
    """
    Load data from the specified source.
    """
    if source == "binance":
        return load_from_binance(**kwargs)
    elif source == "csv":
        return load_from_csv(**kwargs)
    else:
        raise ValueError(f"Unknown data source: {source}")