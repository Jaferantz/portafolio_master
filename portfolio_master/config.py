"""
Configuration module for Portfolio Master.
"""

import os
from pathlib import Path
import getpass

SCRIPT_DIR = Path(__file__).resolve().parent.parent
TRADE_LOG_PATH = SCRIPT_DIR / "trade_log.csv"

def _env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""

CONFIG = {
    "symbol":           "BTCUSDT",
    "capital":          280.0,
    "risk_pct":         0.01,
    "r":                0.01,
    "T":                0.5,
    "S0":               100.0,
    "sigma0":           0.20,
    "hmm_window":       50,
    "alert_every":      5,
    "ofi_depth":        20,
    "ofi_threshold":    0.30,        # ← más exigente para scalping
    "stop_loss_pct":    0.005,       # ← 0.5% stop loss
    "take_profit_pct":  0.008,       # ← 0.8% take profit
    "testnet":          False,
    "runtime_mode":     "paper",
    "binance_key":      _env_first("PM_BINANCE_API_KEY", ""),
    "binance_secret":   _env_first("PM_BINANCE_API_SECRET", ""),
    "telegram_token":   _env_first("PM_TELEGRAM_TOKEN", ""),
    "telegram_chat_id": _env_first("PM_TELEGRAM_CHAT_ID", ""),
    "report_hour":      8,
    "greeks_min_abs_delta": 0.01,
    "greeks_min_abs_gamma": 0.0001,
}

DEFAULT_PORTFOLIO = [
    {'type': 'call', 'K': 100, 'qty':  1},   # call comprada  → delta +
    {'type': 'put',  'K':  95, 'qty':  1},   # put comprada   → delta -
    {'type': 'call', 'K': 105, 'qty': -1},   # call vendida   → delta -
    {'type': 'put',  'K':  98, 'qty': -1},   # put vendida    → delta +
]

# Portafolio balanceado: genera delta + en bull y delta - en bear
# con igual peso en ambas direcciones
