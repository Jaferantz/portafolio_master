"""
Latent Regime Detection bot using Gaussian HMM.
"""

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from portfolio_master.config import CONFIG

class RegimeDetectionBot:
    def __init__(self, n_states=2, window=None):
        self.n_states  = n_states
        self.window    = window if window is not None else CONFIG.get("hmm_window", 50)
        self.model     = None
        self.regime_map = {}

    def compute_features(self, prices: pd.Series) -> pd.DataFrame:
        df = pd.DataFrame({'Close': prices})
        f  = pd.DataFrame(index=df.index)
        f['returns']    = np.log(df['Close']).diff()
        f['volatility'] = f['returns'].rolling(self.window).std()
        f['momentum']   = df['Close'].pct_change(self.window)
        return f.dropna()

    def fit(self, prices: pd.Series):
        features = self.compute_features(prices)
        self.model = GaussianHMM(
            n_components=self.n_states,
            covariance_type="diag",
            n_iter=1000,
            random_state=42,
            tol=0.01
        )
        self.model.fit(features)
        hidden = self.model.predict(features)

        self.regime_map = {}
        for state in np.unique(hidden):
            mask     = hidden == state
            mean_ret = features['returns'][mask].mean()
            mean_vol = features['volatility'][mask].mean()
            if mean_vol < features['volatility'].quantile(0.25):
                regime = 'sideways'
            elif mean_ret < 0:
                regime = 'bear'
            else:
                regime = 'bull'
            self.regime_map[state] = regime

        self.transmat_ = self.model.transmat_
        print(f"  [Regime] Mapa: {self.regime_map}")
        print(f"  [Regime] Transmat:\n{np.round(self.transmat_, 3)}")
        return self

    def detect(self, prices: pd.Series) -> dict:
        features = self.compute_features(prices)
        if self.model is None or len(features) < self.window:
            return {"regime":"sideways","state":1,"probs":[.33,.34,.33],"confidence":0.5}
        hidden = self.model.predict(features)
        probs  = self.model.predict_proba(features)
        state  = hidden[-1]
        return {
            "regime":     self.regime_map.get(state, "sideways"),
            "state":      int(state),
            "probs":      probs[-1].tolist(),
            "confidence": float(max(probs[-1])),
        }