"""
Main orchestrator for the Portfolio Master trading system.
"""

import time
import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from portfolio_master.config import CONFIG, TRADE_LOG_PATH
from portfolio_master.bots.regime_detection import RegimeDetectionBot
from portfolio_master.bots.volatility_surface import VolatilitySurfaceBot
from portfolio_master.bots.delta_gamma_risk import DeltaGammaBot
from portfolio_master.bots.order_flow_imbalance import OrderFlowImbalanceBot
from portfolio_master.execution.position_manager import PositionManager
from portfolio_master.execution.order_executor import OrderExecutor
from portfolio_master.utils.telegram_reporter import TelegramReporter

class PortfolioMasterOrchestrator:
    STATE_FILE = Path(__file__).parent.parent / "dashboard_state.json"

    def __init__(self, mode="paper", prompt_credentials=False, enable_telegram=None, allow_live=False):
        self.mode        = mode
        self.prompt_credentials = prompt_credentials
        self.enable_telegram = enable_telegram
        self.allow_live = allow_live

        # Initialize components
        self.config_update()
        self.telegram = TelegramReporter(
            CONFIG.get("telegram_token",""),
            CONFIG.get("telegram_chat_id","")
        )
        self.regime_bot  = RegimeDetectionBot(window=CONFIG.get("hmm_window", 50))
        self.vol_bot     = VolatilitySurfaceBot()
        self.dg_bot      = DeltaGammaBot()
        self.ofi_bot     = OrderFlowImbalanceBot(
            depth     = CONFIG.get("ofi_depth", 20),
            threshold = CONFIG.get("ofi_threshold", 0.15)
        )
        self.pos_mgr     = PositionManager()
        self.order_executor = OrderExecutor(
            mode=mode,
            prompt_credentials=prompt_credentials,
            allow_live=allow_live
        )
        self.trade_log   = []
        self.pnl         = 0.0
        self._prices     = []
        self._last_report_day   = None
        self._last_regime       = None
        self._last_alert_trade  = 0
        self._load_initial_data()

    def config_update(self):
        """Update CONFIG with runtime mode and loaded credentials."""
        CONFIG["runtime_mode"] = self.mode
        CONFIG["testnet"] = self.mode == "testnet"
        # Note: Credentials are already loaded via environment or will be prompted by OrderExecutor

    def _load_initial_data(self):
        """Download historical prices and train the bots."""
        print("\n+--------------------------------------+")
        print("|    PORTFOLIO MASTER v3.0             |")
        print("+--------------------------------------+")
        mode_label = {
            "paper":   "[PAPER]",
            "testnet": "[TESTNET]",
            "live":    "[LIVE]",
        }.get(self.mode, self.mode.upper())
        print(f"\nModo: {mode_label}")
        print(f"Capital: ${CONFIG['capital']} | Riesgo: {CONFIG['risk_pct']*100}%")
        print(f"Stop Loss: {CONFIG['stop_loss_pct']*100}% | Take Profit: {CONFIG['take_profit_pct']*100}%\n")
        print(f"Log: {TRADE_LOG_PATH}")

        if self.mode in ("testnet", "live"):
            # Connection test is done in OrderExecutor.__init__
            pass

        print("Downloading historical prices from Binance...")
        self._prices = self._fetch_binance(1000)

        print("\n[1/3] Training Regime Detection Bot (HMM)...")
        self.regime_bot.fit(pd.Series(self._prices))

        print("\n[2/3] Training Volatility Surface Bot (RandomForest)...")
        self.vol_bot.train(spot=100)

        print("\n[3/3] Delta-Gamma Bot ready (Black-Scholes)")
        print(f"  Portfolio: {len(self.dg_bot.options)} options")
        print("\n[4/4] Order Flow Imbalance Bot ready")
        print(f"  Depth: {self.ofi_bot.depth} levels | Threshold: {self.ofi_bot.threshold}")
        print("\n[OK] System initialized.\n")
        self.telegram.send_startup(self.regime_bot.regime_map)
        self.telegram.send(
            f"⚡ <b>MODO SCALPING v2 ACTIVADO</b>\n"
            f"SL: {CONFIG['stop_loss_pct']*100}% | TP: {CONFIG['take_profit_pct']*100}%\n"
            f"OFI threshold: {CONFIG['ofi_threshold']}\n"
            f"Interval: 60s\n\n"
            f"<b>Nuevas mejoras:</b>\n"
            f"  📈 EMA20/EMA50 filter — corrects HMM regime\n"
            f"  🔄 BUY + SELL active per real trend\n"
            f"  📊 OFI + Trade pressure as confirmation"
        )

    def _fetch_binance(self, limit=500) -> list:
        """Fetch historical klines from Binance."""
        from portfolio_master.utils.binance_api import fetch_klines
        return fetch_klines(limit=limit)

    def _get_price(self) -> float:
        """Fetch current price from Binance."""
        from portfolio_master.utils.binance_api import get_price
        return get_price()

    def run_once(self) -> dict:
        """Execute one iteration of the trading loop."""
        now   = datetime.now().strftime("%H:%M:%S")
        price = self._get_price()
        self._prices.append(price)
        if len(self._prices) > 1100:
            self._prices = self._prices[-1100:]

        print(f"\n[{now}] {CONFIG['symbol']}: ${price:,.2f}")

        # Initialize state for dashboard
        state = {
            "timestamp": now,
            "price": price,
            "regime": "unknown",
            "trend": "unknown",
            "signal": "NONE",
            "iv": 0.0,
            "delta": 0.0,
            "gamma": 0.0,
            "ofi": 0.0,
            "bid_vol": 0.0,
            "ask_vol": 0.0,
            "pressure": 0.0,
            "pnl": self.pnl,
            "balance": round(CONFIG['capital'] + self.pnl, 4),
            "has_position": self.pos_mgr.has_position(),
            "position_details": None
        }

        # Check open position for SL/TP
        if self.pos_mgr.has_position():
            closed, reason, pnl_real = self.pos_mgr.check(price)
            if closed:
                pnl_real = self.pos_mgr.close(price, reason)
                self.pnl += pnl_real
                pos = self.pos_mgr.closed_trades[-1]
                self._record_position_close(pos, pnl_real, price, reason)
                print(f"  {reason} | Entry: ${pos['entry']:,.2f} → ${price:,.2f} | Real PnL: ${pnl_real:+.4f}")
                self.telegram.send_position_closed(
                    pos['signal'], pos['entry'], price,
                    pos['lots'], pnl_real, reason
                )
                self._save_log()
            else:
                pos = self.pos_mgr.position
                unrealized = self.pos_mgr._calc_pnl(price)
                print(f"  📌 Position {pos['signal']} open @ ${pos['entry']:,.2f} | Unrealized: ${unrealized:+.4f} | SL:${pos['sl']:,.2f} TP:${pos['tp']:,.2f}")
                # Update state for position details
                state["has_position"] = True
                state["position_details"] = {
                    "signal": pos["signal"],
                    "entry": round(pos["entry"], 2),
                    "lots": round(pos["lots"], 5),
                    "sl": round(pos["sl"], 2),
                    "tp": round(pos["tp"], 2),
                    "unrealized_pnl": round(unrealized, 4)
                }
            # Update pnl and balance in state before writing
            state["pnl"] = self.pnl
            state["balance"] = round(CONFIG['capital'] + self.pnl, 4)
            self._write_state(state)
            return {"action": "holding", "price": price}

        # EMA trend filter
        prices_arr = np.array(self._prices[-60:]) if len(self._prices) >= 60 else np.array(self._prices)
        ema20 = pd.Series(prices_arr).ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = pd.Series(prices_arr).ewm(span=50, adjust=False).mean().iloc[-1]
        trend = "up" if ema20 > ema50 else "down"
        print(f"  [TREND] EMA: {'^ BULLISH' if trend=='up' else 'v BEARISH'} (EMA20:{ema20:,.0f} EMA50:{ema50:,.0f})")
        state["trend"] = trend

        # Regime detection
        r      = self.regime_bot.detect(pd.Series(self._prices))
        regime = r['regime']
        conf   = r['confidence']
        print(f"  [REGIME] Regime: {regime.upper()} ({conf:.1%})")
        state["regime"] = regime

        if self._last_regime and self._last_regime != regime:
            self.telegram.send_regime_change(self._last_regime, regime, price, conf)
        self._last_regime = regime

        if regime == "sideways":
            print("  [PAUSE] Sideways - no trading")
            # Update pnl and balance in state before writing
            state["pnl"] = self.pnl
            state["balance"] = round(CONFIG['capital'] + self.pnl, 4)
            self._write_state(state)
            return {"action":"skip","reason":"sideways"}

        # Adjust regime based on EMA trend
        if regime == "bear" and trend == "up":
            regime = "bull"
            print(f"  [UPDATE] Regime corrected: BEAR -> BULL (EMA bullish overrides HMM)")
        elif regime == "bull" and trend == "down":
            regime = "bear"
            print(f"  [UPDATE] Regime corrected: BULL -> BEAR (EMA bearish overrides HMM)")
        state["regime"] = regime  # update after possible correction

        # Volatility forecast
        vol      = self.vol_bot.forecast(S=price, K=price, T=CONFIG['T'])
        iv       = vol['implied_vol']
        risk_amt = CONFIG['capital'] * CONFIG['risk_pct']
        lots     = round(round(risk_amt / price, 5), 5)
        lots     = max(lots, 0.00001)
        print(f"  [VOL] IV: {iv:.1%} | Lots: {lots} (risk: ${risk_amt:.2f})")
        state["iv"] = iv

        # Delta-Gamma signal
        dg     = self.dg_bot.get_signal(sigma=iv, regime=regime)
        signal = dg['signal']
        delta  = dg['delta']
        gamma  = dg['gamma']
        print(f"  [SIGNAL] Delta={delta:.4f} Gamma={gamma:.6f} | Signal: {signal or 'NONE'}")
        state["signal"] = signal if signal else "NONE"
        state["delta"] = delta
        state["gamma"] = gamma

        if not signal:
            print("  [PAUSE] Unfavorable Greeks")
            # Update pnl and balance in state before writing
            state["pnl"] = self.pnl
            state["balance"] = round(CONFIG['capital'] + self.pnl, 4)
            self._write_state(state)
            return {"action":"skip","reason":"no_signal"}

        # Order Flow Imbalance confirmation
        ofi_confirmed, ofi_data = self.ofi_bot.confirms(signal)
        ofi      = ofi_data['ofi']
        bid_vol  = ofi_data['bid_vol']
        ask_vol  = ofi_data['ask_vol']
        pressure = ofi_data.get('pressure', 0)
        print(f"  [OFI] OFI: {ofi:+.4f} | Pressure: {pressure:+.4f} | Bids: {bid_vol:.2f} | Asks: {ask_vol:.2f} | {'[OK] CONFIRMS' if ofi_confirmed else '[NO] CONFIRMS'}")
        state["ofi"] = ofi
        state["bid_vol"] = bid_vol
        state["ask_vol"] = ask_vol
        state["pressure"] = pressure

        if not ofi_confirmed:
            print(f"  [PAUSE] OFI does not confirm signal {signal} (pressure: {ofi_data['signal']})")
            # Update pnl and balance in state before writing
            state["pnl"] = self.pnl
            state["balance"] = round(CONFIG['capital'] + self.pnl, 4)
            self._write_state(state)
            return {"action":"skip","reason":"ofi_rejected"}

        # Execute order
        order, fill_price = self.order_executor.execute(signal, lots, price)
        if not order:
            print("  [PAUSE] Order not executed; no internal position opened.")
            # Update pnl and balance in state before writing
            state["pnl"] = self.pnl
            state["balance"] = round(CONFIG['capital'] + self.pnl, 4)
            self._write_state(state)
            return {"action":"order_failed","signal":signal,"price":price}

        self.pos_mgr.open(signal, fill_price, lots)
        sl = self.pos_mgr.position['sl']
        tp = self.pos_mgr.position['tp']
        print(f"  [POS] Position opened | SL:${sl:,.2f} TP:${tp:,.2f}")

        trade = {
            "timestamp": now, "symbol": CONFIG['symbol'],
            "signal": signal, "price": round(fill_price, 2),
            "lot_size": lots, "regime": regime, "trend": trend,
            "iv": round(iv, 4), "delta": delta, "gamma": gamma,
            "ofi": ofi, "bid_vol": round(bid_vol,4), "ask_vol": round(ask_vol,4),
            "sl": round(sl,2), "tp": round(tp,2),
            "pnl_real": 0.0,
            "pnl_acum": round(self.pnl, 4),
            "balance":  round(CONFIG['capital']+self.pnl, 4),
            "order_id": order.get('orderId') if order else None
        }
        self.trade_log.append(trade)
        n = len(self.trade_log)
        print(f"  [OK] Trade #{n} opened | Accum PnL: ${self.pnl:.4f} | Balance: ${CONFIG['capital']+self.pnl:.4f}")
        self._save_log()

        alert_every = CONFIG.get("alert_every", 5)
        if n == 1 or (n - self._last_alert_trade) >= alert_every:
            self.telegram.send_trade_alert(
                signal, fill_price, lots, regime, iv, delta, gamma,
                self.pnl, n, ofi, bid_vol, ask_vol
            )
            self._last_alert_trade = n

        # Update state for the newly opened position
        state["has_position"] = True
        state["position_details"] = {
            "signal": signal,
            "entry": round(fill_price, 2),
            "lots": lots,
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "unrealized_pnl": 0.0  # just opened, so unrealized is 0
        }
        # Update pnl and balance in state before writing
        state["pnl"] = self.pnl
        state["balance"] = round(CONFIG['capital'] + self.pnl, 4)
        self._write_state(state)
        return trade

    def _save_log(self):
        """Save trade log to CSV."""
        if self.trade_log:
            TRADE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(self.trade_log).to_csv(TRADE_LOG_PATH, index=False)

    def _write_state(self, state_dict: dict):
        """Write the state dictionary to the dashboard state file."""
        try:
            self.STATE_FILE.write_text(json.dumps(state_dict, indent=2))
        except Exception as e:
            print(f"  [WARN] Could not write dashboard state: {e}")

    def _record_position_close(self, pos: dict, pnl_real: float, exit_price: float, reason: str):
        """Record a closed position in the trade log."""
        for trade in reversed(self.trade_log):
            same_position = (
                trade.get("signal") == pos.get("signal") and
                abs(float(trade.get("price", 0)) - float(pos.get("entry", 0))) < 0.01 and
                float(trade.get("pnl_real", 0) or 0) == 0
            )
            if same_position:
                trade.update({
                    "exit_price": round(exit_price, 2),
                    "exit_reason": reason,
                    "exit_time": pos.get("exit_time"),
                    "pnl_real": round(pnl_real, 4),
                    "pnl_acum": round(self.pnl, 4),
                    "balance": round(CONFIG['capital'] + self.pnl, 4),
                })
                return

        self.trade_log.append({
            "timestamp": pos.get("time"),
            "symbol": CONFIG['symbol'],
            "signal": pos.get("signal"),
            "price": round(pos.get("entry", 0), 2),
            "lot_size": pos.get("lots"),
            "exit_price": round(exit_price, 2),
            "exit_reason": reason,
            "exit_time": pos.get("exit_time"),
            "pnl_real": round(pnl_real, 4),
            "pnl_acum": round(self.pnl, 4),
            "balance": round(CONFIG['capital'] + self.pnl, 4),
        })

    def run_loop(self, interval=300):
        """Run the trading loop indefinitely."""
        print(f"Loop started. Cycle every {interval}s. Press Ctrl+C to stop.\n")
        try:
            while True:
                now = datetime.now()
                report_hour = CONFIG.get("report_hour", 8)
                if now.hour == report_hour and self._last_report_day != now.date():
                    r = self.regime_bot.detect(pd.Series(self._prices))
                    self.telegram.send_daily_report(self.trade_log, self.pnl, r.get("regime","sideways"))
                    self._last_report_day = now.date()
                    print(f"  [MSG] Daily report sent")

                try:
                    self.run_once()
                except Exception as e:
                    print(f"  [WARN] Error in cycle: {e}")
                    self.telegram.send_error(str(e))

                print(f"  [TIME] Next cycle in {interval}s...")
                time.sleep(interval)

        except KeyboardInterrupt:
            # Close any open position on exit
            if self.pos_mgr.has_position():
                price = self._get_price()
                pnl   = self.pos_mgr.close(price, "[STOP] Bot stopped manually")
                self.pnl += pnl
                print(f"\n  Position closed on stop: PnL ${pnl:+.4f}")

            s = self.pos_mgr.summary()
            print(f"\n\nBot stopped.")
            print(f"Closed trades: {s['trades']} | Real PnL: ${s['pnl_real']:+.4f}")
            print(f"Wins: {s['wins']} | Losses: {s['losses']} | Win rate: {s['winrate']}%")
            self._save_log()
            print(f"Log saved to {TRADE_LOG_PATH}")