"""
Binance API utilities for fetching market data and signing requests.
"""

import time
import json
import urllib.request
import urllib.parse
import hashlib as _hl
import hmac as _hm
import numpy as np
from portfolio_master.config import CONFIG

def get_base_url(mode: str) -> str:
    """Get the base URL for Binance API based on mode."""
    return (
        "https://testnet.binance.vision/api/v3"
        if mode == "testnet" else
        "https://api.binance.com/api/v3"
    )

def get_price(symbol: str = None) -> float:
    """Fetch the current price for a symbol from Binance."""
    symbol = symbol or CONFIG["symbol"]
    try:
        query = urllib.parse.urlencode({"symbol": symbol})
        url  = f"https://api.binance.com/api/v3/ticker/price?{query}"
        data = json.loads(urllib.request.urlopen(url, timeout=5).read())
        return float(data['price'])
    except Exception:
        # Fallback to last known price or a default
        return 67000.0  # Default fallback

def fetch_klines(symbol: str = None, interval: str = "1h", limit: int = 500) -> list:
    """Fetch historical klines (candlesticks) from Binance."""
    symbol = symbol or CONFIG["symbol"]
    try:
        query = urllib.parse.urlencode({
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        })
        url  = f"https://api.binance.com/api/v3/klines?{query}"
        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
        # Extract closing prices
        prices = [float(c[4]) for c in data]
        return prices
    except Exception as e:
        print(f"  ✗ Error Binance API: {e} — using simulated prices")
        base = 67000
        p = [base]
        for _ in range(limit-1):
            p.append(p[-1]*(1+np.random.normal(0.0002, 0.015)))
        return p

def signed_request(method: str, path: str, params: dict = None, base_url: str = None) -> dict:
    """Make a signed request to Binance API."""
    base   = base_url or get_base_url(CONFIG["runtime_mode"])
    params = dict(params) if params else {}

    try:
        t_url = f"{base}/time"
        t_res = json.loads(urllib.request.urlopen(t_url, timeout=5).read())
        params['timestamp'] = t_res['serverTime']
    except Exception:
        params['timestamp'] = int(time.time() * 1000)

    params['recvWindow'] = 60000
    query  = urllib.parse.urlencode(params)
    sig    = _hm.new(CONFIG['binance_secret'].encode(), query.encode(), _hl.sha256).hexdigest()

    if method == "POST":
        full_query = f"{query}&signature={sig}"
        url = f"{base}{path}"
        req = urllib.request.Request(
            url, data=full_query.encode(), method="POST",
            headers={
                'X-MBX-APIKEY': CONFIG['binance_key'],
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
    else:
        url = f"{base}{path}?{query}&signature={sig}"
        req = urllib.request.Request(url, method=method,
                                      headers={'X-MBX-APIKEY': CONFIG['binance_key']})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    except urllib.error.HTTPError as e:
        print(f"  [Binance {CONFIG['runtime_mode'].upper()}] Error {e.code}: {e.read().decode()}")
        return {}
    except urllib.error.URLError as e:
        print(f"  [Binance {CONFIG['runtime_mode'].upper()}] Error de red: {e}")
        return {}

def get_account_balance() -> dict:
    """Get account balances from Binance."""
    balance = signed_request("GET", "/account")
    if balance:
        # Extract USDT and BTC free balances
        usdt = next((float(b['free']) for b in balance['balances'] if b['asset'] == 'USDT'), 0)
        btc  = next((float(b['free']) for b in balance['balances'] if b['asset'] == 'BTC'), 0)
        return {'USDT': usdt, 'BTC': btc}
    return {}