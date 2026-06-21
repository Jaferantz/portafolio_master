"""
Performance metrics for backtesting.
"""

import numpy as np
import pandas as pd

def calculate_returns(equity_curve: pd.Series) -> pd.Series:
    """
    Calculate periodic returns from an equity curve.
    """
    return equity_curve.pct_change().fillna(0)

def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 365*24) -> float:
    """
    Calculate the Sharpe ratio.
    Assumes returns are in the same period as risk_free_rate (e.g., daily returns with annual risk-free rate).
    """
    excess_returns = returns - risk_free_rate / periods_per_year
    if excess_returns.std() == 0:
        return 0.0
    return np.sqrt(periods_per_year) * excess_returns.mean() / excess_returns.std()

def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 365*24) -> float:
    """
    Calculate the Sortino ratio (downside deviation).
    """
    excess_returns = returns - risk_free_rate / periods_per_year
    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) == 0:
        return np.inf
    downside_deviation = np.sqrt(np.mean(downside_returns**2))
    if downside_deviation == 0:
        return 0.0
    return np.sqrt(periods_per_year) * excess_returns.mean() / downside_deviation

def max_drawdown(equity_curve: pd.Series) -> float:
    """
    Calculate the maximum drawdown.
    """
    rolling_max = equity_curve.expanding().max()
    drawdown = (equity_curve - rolling_max) / rolling_max
    return drawdown.min()  # Most negative (largest drawdown)

def win_rate(trades: list) -> float:
    """
    Calculate the win rate from a list of trades.
    Each trade should have a 'pnl' field.
    """
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
    return wins / len(trades)

def profit_factor(trades: list) -> float:
    """
    Calculate the profit factor (gross profit / gross loss).
    """
    if not trades:
        return 0.0
    profits = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
    losses = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
    if losses == 0:
        return np.inf if profits > 0 else 0.0
    return profits / losses

def calculate_metrics(equity_curve: pd.Series, trades: list, risk_free_rate: float = 0.0) -> dict:
    """
    Calculate a set of performance metrics.
    """
    returns = calculate_returns(equity_curve)
    return {
        'sharpe_ratio': sharpe_ratio(returns, risk_free_rate),
        'sortino_ratio': sortino_ratio(returns, risk_free_rate),
        'max_drawdown': max_drawdown(equity_curve),
        'win_rate': win_rate(trades),
        'profit_factor': profit_factor(trades),
        'total_return': (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1 if len(equity_curve) > 1 else 0,
        'volatility': returns.std() * np.sqrt(365*24),  # Annualized volatility assuming hourly data
    }