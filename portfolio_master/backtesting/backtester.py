"""
Backtesting engine for the Portfolio Master strategy.
"""

import pandas as pd
import numpy as np
from datetime import timedelta
from portfolio_master.config import CONFIG
from portfolio_master.backtesting.data_loader import load_data
from portfolio_master.backtesting.metrics import calculate_metrics

class Backtester:
    def __init__(self, data: pd.DataFrame, initial_capital: float = None):
        """
        Initialize the backtester with historical data.
        DataFrame must have a datetime index and columns: ['open', 'high', 'low', 'close', 'volume']
        """
        self.data = data.copy()
        # Use close price for trading signals
        self.close_prices = self.data['close']
        self.initial_capital = initial_capital if initial_capital is not None else CONFIG['capital']
        self.capital = self.initial_capital
        self.position = None  # Current position: dict or None
        self.trades = []      # List of completed trades
        self.equity_curve = [] # Equity over time (including open positions)
        self.timestamps = []   # Timestamp for each equity point

        # Initialize bots (using the same parameters as live)
        from portfolio_master.bots.regime_detection import RegimeDetectionBot
        from portfolio_master.bots.volatility_surface import VolatilitySurfaceBot
        from portfolio_master.bots.delta_gamma_risk import DeltaGammaBot
        from portfolio_master.bots.order_flow_imbalance import OrderFlowImbalanceBot

        self.regime_bot  = RegimeDetectionBot(window=CONFIG.get("hmm_window", 50))
        self.vol_bot     = VolatilitySurfaceBot()
        self.dg_bot      = DeltaGammaBot()
        self.ofi_bot     = OrderFlowImbalanceBot(
            depth     = CONFIG.get("ofi_depth", 20),
            threshold = CONFIG.get("ofi_threshold", 0.15)
        )

        # Train bots on the entire dataset (or a training period?)
        # For simplicity, we train on the whole dataset (may cause lookahead bias)
        # In practice, we should use a rolling window or expanding window.
        # We'll train on the first 80% of data to avoid lookahead bias.
        split_idx = int(len(self.data) * 0.8)
        train_data = self.data.iloc[:split_idx]
        print("Training bots on historical data (first 80% to avoid lookahead bias)...")
        self.regime_bot.fit(pd.Series(train_data['close']))
        self.vol_bot.train(spot=train_data['close'].iloc[-1])
        print("Bots trained.")

    def _get_price_at(self, idx: int) -> float:
        """Get the close price at a given index."""
        return self.close_prices.iloc[idx]

    def _update_equity(self, timestamp: pd.Timestamp, price: float):
        """Update the equity curve with current capital and position value."""
        equity = self.capital
        if self.position:
            # Calculate unrealized PnL of the open position
            if self.position['signal'] == 'BUY':
                unrealized = (price - self.position['entry']) * self.position['lots']
            else:
                unrealized = (self.position['entry'] - price) * self.position['lots']
            equity += unrealized
        self.equity_curve.append(equity)
        self.timestamps.append(timestamp)

    def run(self, start_idx: int = None, end_idx: int = None):
        """
        Run the backtest on the historical data.
        """
        start_idx = start_idx if start_idx is not None else 50  # Need some data for indicators
        end_idx   = end_idx if end_idx is not None else len(self.data)

        print(f"Running backtest from index {start_idx} to {end_idx} ({end_idx - start_idx} candles)...")

        for i in range(start_idx, end_idx):
            timestamp = self.data.index[i]
            price = self._get_price_at(i)

            # Update equity curve (mark-to-market)
            self._update_equity(timestamp, price)

            # Check if we need to close the position due to SL/TP
            if self.position:
                # For simplicity, we use the high and low of the candle to check SL/TP
                high = self.data['high'].iloc[i]
                low  = self.data['low'].iloc[i]
                closed = False
                reason = ""
                pnl_real = 0.0

                if self.position['signal'] == 'BUY':
                    if low <= self.position['sl']:
                        closed = True
                        reason = "🛑 STOP LOSS"
                        exit_price = self.position['sl']
                    elif high >= self.position['tp']:
                        closed = True
                        reason = "✅ TAKE PROFIT"
                        exit_price = self.position['tp']
                else:  # SELL
                    if high >= self.position['sl']:
                        closed = True
                        reason = "🛑 STOP LOSS"
                        exit_price = self.position['sl']
                    elif low <= self.position['tp']:
                        closed = True
                        reason = "✅ TAKE PROFIT"
                        exit_price = self.position['tp']

                if closed:
                    # Calculate PnL
                    if self.position['signal'] == 'BUY':
                        pnl_real = (exit_price - self.position['entry']) * self.position['lots']
                    else:
                        pnl_real = (self.position['entry'] - exit_price) * self.position['lots']
                    self.capital += pnl_real
                    self.trades.append({
                        'entry_time': self.position['entry_time'],
                        'exit_time': timestamp,
                        'signal': self.position['signal'],
                        'entry_price': self.position['entry'],
                        'exit_price': exit_price,
                        'lots': self.position['lots'],
                        'pnl': pnl_real,
                        'reason': reason
                    })
                    self.position = None  # Position closed

            # If no position, look for a new signal
            if not self.position:
                # We need a window of data up to the current point to compute indicators
                # We'll use data from 0 to i (inclusive) to simulate information available at time i
                window_data = self.data.iloc[:i+1]
                if len(window_data) < 50:  # Need minimum data for indicators
                    continue

                # --- Regime Detection ---
                regime_result = self.regime_bot.detect(pd.Series(window_data['close']))
                regime = regime_result['regime']
                conf   = regime_result['confidence']

                if regime == "sideways":
                    continue  # No trade in sideways regime

                # --- EMA Trend Filter ---
                closes = window_data['close']
                ema20 = closes.ewm(span=20, adjust=False).mean().iloc[-1]
                ema50 = closes.ewm(span=50, adjust=False).mean().iloc[-1]
                trend = "up" if ema20 > ema50 else "down"

                # Adjust regime based on EMA
                if regime == "bear" and trend == "up":
                    regime = "bull"
                elif regime == "bull" and trend == "down":
                    regime = "bear"

                # --- Volatility Forecast ---
                vol_result = self.vol_bot.forecast(S=price, K=price, T=CONFIG['T'])
                iv = vol_result['implied_vol']
                risk_amt = self.capital * CONFIG['risk_pct']
                lots = round(round(risk_amt / price, 5), 5)
                lots = max(lots, 0.00001)

                # --- Delta-Gamma Signal ---
                dg_result = self.dg_bot.get_signal(sigma=iv, regime=regime)
                signal = dg_result['signal']
                delta  = dg_result['delta']
                gamma  = dg_result['gamma']

                if not signal:
                    continue  # No signal from Greeks

                # --- Order Flow Imbalance (simplified for backtesting) ---
                # In backtesting, we don't have real order book, so we simulate OFI based on volume imbalance
                # We'll use the volume of the current candle as a proxy for buying/selling pressure
                # This is a simplification; in reality, OFI requires order book data.
                # For now, we'll skip OFI confirmation in backtesting or use a volume-based proxy.
                # We'll use the volume delta (buy volume - sell volume) but we don't have that.
                # Instead, we'll use the close price relative to open: if close > open, buying pressure.
                # This is very rough.
                open_price = self.data['open'].iloc[i]
                close_price = price
                volume = self.data['volume'].iloc[i]
                # Simple proxy: if close > open, buying pressure; else selling pressure
                if close_price > open_price:
                    ofi_signal = "buy"
                else:
                    ofi_signal = "sell"
                # We'll assume it confirms if the signal matches
                ofi_confirmed = (signal == "BUY" and ofi_signal == "buy") or (signal == "SELL" and ofi_signal == "sell")

                if not ofi_confirmed:
                    continue  # OFI does not confirm

                # --- Execute Trade ---
                # Calculate SL and TP
                if signal == "BUY":
                    sl = price * (1 - CONFIG['stop_loss_pct'])
                    tp = price * (1 + CONFIG['take_profit_pct'])
                else:
                    sl = price * (1 + CONFIG['stop_loss_pct'])
                    tp = price * (1 - CONFIG['take_profit_pct'])

                # Open position
                self.position = {
                    'signal': signal,
                    'entry': price,
                    'lots': lots,
                    'sl': sl,
                    'tp': tp,
                    'entry_time': timestamp
                }

        # After loop, close any open position at the last price
        if self.position:
            last_price = self.close_prices.iloc[-1]
            if self.position['signal'] == 'BUY':
                pnl_real = (last_price - self.position['entry']) * self.position['lots']
            else:
                pnl_real = (self.position['entry'] - last_price) * self.position['lots']
            self.capital += pnl_real
            self.trades.append({
                'entry_time': self.position['entry_time'],
                'exit_time': self.data.index[-1],
                'signal': self.position['signal'],
                'entry_price': self.position['entry'],
                'exit_price': last_price,
                'lots': self.position['lots'],
                'pnl': pnl_real,
                'reason': "🏁 End of backtest"
            })
            self.position = None

        # Final equity update
        self._update_equity(self.data.index[-1], self.close_prices.iloc[-1])

        print(f"Backtest completed. Initial capital: ${self.initial_capital:,.2f}, Final capital: ${self.capital:,.2f}")
        print(f"Number of trades: {len(self.trades)}")

        # Calculate equity curve as a Series
        self.equity_series = pd.Series(self.equity_curve, index=self.timestamps)
        return self

    def get_results(self):
        """
        Return the backtest results.
        """
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_return': (self.capital / self.initial_capital) - 1,
            'trades': self.trades,
            'equity_curve': self.equity_series,
            'metrics': calculate_metrics(self.equity_series, self.trades)
        }