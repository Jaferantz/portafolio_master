"""
Position manager for tracking open positions and calculating real PnL.
"""

from portfolio_master.config import CONFIG

class PositionManager:
    """
    Tracks open positions and calculates real PnL.
    Closes position when SL, TP is reached or on opposite signal.
    """
    def __init__(self):
        self.position    = None   # active position: {signal, entry, lots, sl, tp, time}
        self.real_pnl    = 0.0    # accumulated real PnL
        self.closed_trades = []   # history of closed trades

    def open(self, signal: str, price: float, lots: float):
        sl = price*(1-CONFIG['stop_loss_pct'])   if signal=="BUY" else price*(1+CONFIG['stop_loss_pct'])
        tp = price*(1+CONFIG['take_profit_pct']) if signal=="BUY" else price*(1-CONFIG['take_profit_pct'])
        self.position = {
            "signal": signal, "entry": price,
            "lots": lots, "sl": sl, "tp": tp,
            "time": None  # Time will be set by the caller if needed
        }

    def check(self, current_price: float) -> tuple:
        """
        Check if the position hit SL or TP.
        Returns (closed: bool, reason: str, pnl_real: float)
        """
        if not self.position:
            return False, "", 0.0

        p   = self.position
        sig = p['signal']

        hit_sl = (sig=="BUY"  and current_price <= p['sl']) or \
                 (sig=="SELL" and current_price >= p['sl'])
        hit_tp = (sig=="BUY"  and current_price >= p['tp']) or \
                 (sig=="SELL" and current_price <= p['tp'])

        if hit_sl:
            return True, "🛑 STOP LOSS", self._calc_pnl(current_price)
        if hit_tp:
            return True, "✅ TAKE PROFIT", self._calc_pnl(current_price)
        return False, "", 0.0

    def close(self, exit_price: float, reason: str) -> float:
        if not self.position:
            return 0.0
        pnl = self._calc_pnl(exit_price)
        self.real_pnl += pnl
        self.closed_trades.append({
            **self.position,
            "exit":    exit_price,
            "pnl_real": round(pnl, 4),
            "reason":  reason,
            "exit_time": None  # To be set by caller
        })
        self.position = None
        return pnl

    def _calc_pnl(self, exit_price: float) -> float:
        p = self.position
        if p['signal'] == "BUY":
            return (exit_price - p['entry']) * p['lots']
        else:
            return (p['entry'] - exit_price) * p['lots']

    def has_position(self) -> bool:
        return self.position is not None

    def summary(self) -> dict:
        if not self.closed_trades:
            return {"trades": 0, "pnl_real": 0, "wins": 0, "losses": 0, "winrate": 0}
        wins   = sum(1 for t in self.closed_trades if t['pnl_real'] > 0)
        losses = sum(1 for t in self.closed_trades if t['pnl_real'] <= 0)
        return {
            "trades":   len(self.closed_trades),
            "pnl_real": round(self.real_pnl, 4),
            "wins":     wins,
            "losses":   losses,
            "winrate":  round(wins/len(self.closed_trades)*100, 1) if self.closed_trades else 0
        }