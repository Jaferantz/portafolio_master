"""
Volatility Surface Forecasting bot using RandomForest.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from portfolio_master.config import CONFIG

class VolatilitySurfaceBot:
    def __init__(self):
        self.model   = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)
        self.trained = False

    def _simulate_data(self, n=1000, spot=100):
        np.random.seed(42)
        K  = np.random.uniform(80, 120, n)
        T  = np.random.uniform(0.05, 2, n)
        iv = 0.15 + 0.25*np.exp(-T)*np.exp(-((K/spot-1)**2)/0.1) + np.random.normal(0,.01,n)
        return pd.DataFrame({'strike':K,'maturity':T,'implied_volatility':iv,'spot':spot})

    def _features(self, df):
        df = df.copy()
        df['moneyness']             = df['strike'] / df['spot']
        df['time_to_maturity']      = df['maturity']
        df['historical_volatility'] = 0.18 + 0.05*np.exp(-df['maturity'])
        return df

    def train(self, spot=100):
        df = self._features(self._simulate_data(spot=spot))
        X  = df[['moneyness','time_to_maturity','historical_volatility']].values
        y  = df['implied_volatility'].values
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_tr, y_tr)
        self.trained = True
        y_pred = self.model.predict(X_te)
        mse = np.mean((y_te-y_pred)**2)
        r2  = 1 - np.sum((y_te-y_pred)**2)/np.sum((y_te-y_te.mean())**2)
        print(f"  [VolSurface] MSE: {mse:.6f}, R²: {r2:.4f}")
        return self

    def forecast(self, S: float, K: float, T: float) -> dict:
        moneyness = K / S
        hist_vol  = 0.18 + 0.05*np.exp(-T)
        if self.trained:
            iv = float(self.model.predict([[moneyness, T, hist_vol]])[0])
        else:
            iv = 0.15 + 0.25*np.exp(-T)*np.exp(-((moneyness-1)**2)/0.1)
        iv       = max(iv, 0.01)
        lot_size = max(round((CONFIG['capital']*CONFIG['risk_pct'])/(iv*CONFIG['capital']), 4), 0.0001)
        return {"implied_vol": iv, "lot_size": lot_size}