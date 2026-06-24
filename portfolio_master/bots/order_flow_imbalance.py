"""
Order Flow Imbalance bot using Binance order book and trade data.
"""

import time
import json
import urllib.request
import urllib.parse
from portfolio_master.utils.binance_api import get_price, signed_request
from portfolio_master.config import CONFIG

class OrderFlowImbalanceBot:
    def __init__(self, depth=20, threshold=0.15):
        self.depth     = depth
        self.threshold = threshold
        self.history   = []

    def fetch_orderbook(self) -> dict:
        try:
            query = urllib.parse.urlencode({"symbol": CONFIG["symbol"], "limit": self.depth})
            url  = f"https://api.binance.com/api/v3/depth?{query}"
            data = json.loads(urllib.request.urlopen(url, timeout=5).read())
            return {
                "bids": [[float(p), float(v)] for p, v in data['bids']],
                "asks": [[float(p), float(v)] for p, v in data['asks']],
            }
        except Exception as e:
            print(f"  [OFI] Error fetching order book: {e}")
            return {"bids": [], "asks": []}

    def fetch_trade_pressure(self) -> float:
        """
        Pressure of recent trades: ratio buy vs sell in last 50 trades.
        Useful for scalping — confirms immediate momentum.
        """
        try:
            query = urllib.parse.urlencode({"symbol": CONFIG["symbol"], "limit": 50})
            url  = f"https://api.binance.com/api/v3/trades?{query}"
            data = json.loads(urllib.request.urlopen(url, timeout=5).read())
            buys  = sum(float(t['qty']) for t in data if not t['isBuyerMaker'])
            sells = sum(float(t['qty']) for t in data if t['isBuyerMaker'])
            total = buys + sells
            return (buys - sells) / total if total > 0 else 0.0
        except:
            return 0.0

    def calculate(self) -> dict:
        book    = self.fetch_orderbook()
        bids    = book['bids']
        asks    = book['asks']
        if not bids or not asks:
            return {"ofi":0.0,"signal":"neutral","bid_vol":0,"ask_vol":0,"confirmed":False,"pressure":0}

        bid_vol = sum(v for _, v in bids)
        ask_vol = sum(v for _, v in asks)
        total   = bid_vol + ask_vol
        ofi     = (bid_vol - ask_vol) / total if total > 0 else 0.0

        # Pressure of recent trades (scalping)
        pressure = self.fetch_trade_pressure()

        self.history.append(ofi)
        if len(self.history) > 20:
            self.history = self.history[-20:]

        if   ofi > self.threshold:  signal = "buy"
        elif ofi < -self.threshold: signal = "sell"
        else:                       signal = "neutral"

        return {
            "ofi":      round(ofi, 4),
            "signal":   signal,
            "bid_vol":  round(bid_vol, 4),
            "ask_vol":  round(ask_vol, 4),
            "pressure": round(pressure, 4),
        }

    def confirms(self, trade_signal: str) -> tuple:
        data = self.calculate()
        pressure = data['pressure']

        # For scalping: OFI + trade pressure must coincide
        ofi_ok  = (trade_signal=="BUY"  and data['signal']=="buy") or \
                  (trade_signal=="SELL" and data['signal']=="sell")
        pres_ok = (trade_signal=="BUY"  and pressure > 0) or \
                  (trade_signal=="SELL" and pressure < 0)

        confirmed = ofi_ok and pres_ok
        data['confirmed'] = confirmed
        return confirmed, data