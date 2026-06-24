"""
Delta-Gamma Risk Surface bot using Black-Scholes.
"""

import numpy as np
from scipy.stats import norm
from portfolio_master.config import CONFIG

DEFAULT_PORTFOLIO = [
    {'type': 'call', 'K': 100, 'qty':  1},   # call comprada  → delta +
    {'type': 'put',  'K':  95, 'qty':  1},   # put comprada   → delta -
    {'type': 'call', 'K': 105, 'qty': -1},   # call vendida   → delta -
    {'type': 'put',  'K':  98, 'qty': -1},   # put vendida    → delta +
]

class DeltaGammaBot:
    def __init__(self, options=None):
        self.options = options or DEFAULT_PORTFOLIO

    def _delta(self, S, K, T, r, sigma, otype='call'):
        d1 = (np.log(S/K)+(r+.5*sigma**2)*T)/(sigma*np.sqrt(T))
        return norm.cdf(d1) if otype=='call' else norm.cdf(d1)-1

    def _gamma(self, S, K, T, r, sigma):
        d1 = (np.log(S/K)+(r+.5*sigma**2)*T)/(sigma*np.sqrt(T))
        return norm.pdf(d1)/(S*sigma*np.sqrt(T))

    def portfolio_greeks(self, S, sigma, T, r):
        td, tg = 0.0, 0.0
        for o in self.options:
            td += self._delta(S, o['K'], T, r, sigma, o['type']) * o['qty']
            tg += self._gamma(S, o['K'], T, r, sigma) * o['qty']
        return td, tg

    def get_signal(self, sigma: float, regime: str) -> dict:
        T, r = CONFIG['T'], CONFIG['r']
        if regime == "sideways":
            return {"signal": None, "delta": 0, "gamma": 0}

        d, g = self.portfolio_greeks(100, sigma, T, r)

        min_delta = CONFIG.get("greeks_min_abs_delta", 0.01)
        min_gamma = CONFIG.get("greeks_min_abs_gamma", 0.0001)
        greeks_ok = abs(d) >= min_delta and abs(g) >= min_gamma

        if   regime == "bull" and greeks_ok: signal = "BUY"
        elif regime == "bear" and greeks_ok: signal = "SELL"
        else:                                signal = None

        return {"signal": signal, "delta": round(d,6), "gamma": round(g,6)}