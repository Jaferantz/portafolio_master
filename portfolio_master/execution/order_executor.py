"""
Order executor for simulating or sending orders to Binance.
"""

import time
import json
import urllib.request
import urllib.parse
import hashlib as _hl
import hmac as _hm
from portfolio_master.config import CONFIG
from portfolio_master.utils.binance_api import get_base_url

class OrderExecutor:
    def __init__(self, mode="paper", prompt_credentials=False, allow_live=False):
        self.mode        = mode
        if self.mode == "live" and not allow_live:
            raise RuntimeError("LIVE mode requires --confirm-live to avoid accidental real orders.")

        CONFIG["runtime_mode"] = self.mode
        CONFIG["testnet"] = self.mode == "testnet"

        self._binance_connected = False
        self._base_url = get_base_url(self.mode)
        self._load_credentials(prompt_credentials)

    def _load_credentials(self, prompt_credentials: bool):
        if self.mode in ("testnet", "live"):
            from ..utils.binance_api import signed_request  # Avoid circular import at module level
            # We'll load credentials from CONFIG which is already set by environment or prompt
            if prompt_credentials:
                # This method is called from PortfolioMaster, which already prompted if needed.
                pass

            # Check if credentials are available
            if not CONFIG["binance_key"] or not CONFIG["binance_secret"]:
                raise RuntimeError(
                    "Missing Binance credentials. Use --prompt-credentials or set "
                    "PM_BINANCE_API_KEY and PM_BINANCE_API_SECRET."
                )

            # Test connection
            try:
                bal = self._signed_request("GET", "/account")
                if bal:
                    usdt = next((float(b['free']) for b in bal['balances'] if b['asset'] == 'USDT'), 0)
                    btc  = next((float(b['free']) for b in bal['balances'] if b['asset'] == 'BTC'), 0)
                    if usdt > 0:
                        CONFIG['capital'] = usdt
                    print(f"✓ Binance {self.mode.upper()} connected")
                    print(f"  💰 USDT: ${usdt:,.2f} | BTC: {btc:.4f}")
                    print(f"  📦 Risk per trade: ${CONFIG['capital']*CONFIG['risk_pct']:.2f}")
                    self._binance_connected = True
            except Exception as e:
                print(f"✗ Binance {self.mode.upper()} connection error: {e}")
                print("  → Real/testnet orders will be blocked until reconnected.")
                self._binance_connected = False

    def _signed_request(self, method: str, path: str, params: dict = None) -> dict:
        """Make a signed request to Binance API."""
        base   = self._base_url
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
            print(f"  [Binance {self.mode.upper()}] Error {e.code}: {e.read().decode()}")
            return {}
        except urllib.error.URLError as e:
            print(f"  [Binance {self.mode.upper()}] Network error: {e}")
            return {}

    def execute(self, signal: str, lots: float, price: float):
        """Execute an order and return (order_info, fill_price)."""
        if self.mode == "paper":
            print(f"  [PAPER] {signal} {lots} {CONFIG['symbol']} @ ${price:,.2f}")
            return {"orderId": f"PAPER-{int(time.time())}", "status":"filled"}, price

        if self.mode in ("testnet", "live"):
            if not self._binance_connected:
                print(f"  ✗ Binance {self.mode.upper()} not connected; order blocked.")
                return None, price
            try:
                params = {"symbol": CONFIG['symbol'],
                          "side":   "BUY" if signal=="BUY" else "SELL",
                          "type":   "MARKET",
                          "quantity": lots}
                order = self._signed_request("POST", "/order", params)
                if order and 'orderId' in order:
                    fill = float(order.get('fills',[{}])[0].get('price', price)) if order.get('fills') else price
                    print(f"  ✓ Binance {self.mode.upper()} executed #{order['orderId']} @ ${fill:,.2f}")
                    return order, fill
                else:
                    print(f"  ✗ Binance {self.mode.upper()} order error: {order}")
                    return None, price
            except Exception as e:
                print(f"  ✗ Error executing on Binance {self.mode.upper()}: {e}")
                return None, price

        print(f"  ✗ Unknown mode: {self.mode}")
        return None, price