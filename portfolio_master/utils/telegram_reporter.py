"""
Telegram reporter module for sending alerts and reports.
"""

import urllib.request
import urllib.parse
import json
from datetime import datetime
from portfolio_master.config import CONFIG

class TelegramReporter:
    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)

    def send(self, message: str):
        if not self.enabled:
            return
        try:
            url  = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": self.chat_id, "text": message, "parse_mode": "HTML"
            }).encode()
            urllib.request.urlopen(url, data=data, timeout=10)
        except Exception as e:
            print(f"  [Telegram] Error: {e}")

    def send_startup(self, regime_map: dict):
        msg = (
            f"🚀 <b>PORTFOLIO MASTER v3.0 INICIADO</b>\n"
            f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
            f"<b>Capital:</b> ${CONFIG['capital']}\n"
            f"<b>Símbolo:</b> {CONFIG['symbol']}\n"
            f"<b>Riesgo/trade:</b> {CONFIG['risk_pct']*100}%\n"
            f"<b>Alertas:</b> cada {CONFIG['alert_every']} trades o cambio de régimen\n\n"
            f"<b>Pipeline activo:</b>\n"
            f"  🧭 HMM Regime Detection\n"
            f"  📏 RandomForest Vol Surface\n"
            f"  🎯 Black-Scholes Delta-Gamma\n"
            f"  📊 Order Flow Imbalance (depth={CONFIG['ofi_depth']}, threshold={CONFIG['ofi_threshold']})\n\n"
            f"<b>Mapa HMM:</b>\n"
            + "\n".join([f"  Estado {k}: {v}" for k,v in regime_map.items()])
            + f"\n\n✅ VPS 24/7 activo"
        )
        self.send(msg)

    def send_trade_alert(self, signal: str, price: float, lots: float,
                         regime: str, iv: float, delta: float, gamma: float,
                         pnl: float, trade_count: int, ofi: float,
                         bid_vol: float, ask_vol: float):
        icon     = "🟢 BUY" if signal == "BUY" else "🔴 SELL"
        pnl_icon = "📈" if pnl >= 0 else "📉"
        balance  = CONFIG['capital'] + pnl
        ofi_bar  = "█" * int(abs(ofi) * 10) + "░" * (10 - int(abs(ofi) * 10))
        msg = (
            f"{icon} <b>TRADE #{trade_count}</b>\n"
            f"💲 Precio: ${price:,.2f}\n"
            f"📦 Lotes: {lots}\n"
            f"🧭 Régimen: {regime.upper()}\n"
            f"📏 IV: {iv:.1%}\n"
            f"Δ {delta:.4f} | Γ {gamma:.6f}\n"
            f"📊 OFI: {ofi:+.4f} [{ofi_bar}]\n"
            f"  Bids: {bid_vol:.2f} BTC | Asks: {ask_vol:.2f} BTC\n"
            f"{pnl_icon} PnL sesión: ${pnl:+.4f}\n"
            f"💰 Balance: ${balance:.4f}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(msg)

    def send_regime_change(self, old: str, new: str, price: float, conf: float):
        icons = {"bull":"🐂", "bear":"🐻", "sideways":"😴"}
        msg = (
            f"🔄 <b>CAMBIO DE RÉGIMEN</b>\n"
            f"{icons.get(old,'❓')} {old.upper()} → {icons.get(new,'❓')} {new.upper()}\n"
            f"💲 Precio: ${price:,.2f}\n"
            f"🎯 Confianza: {conf:.1%}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(msg)

    def send_position_closed(self, signal: str, entry: float, exit_price: float,
                              lots: float, pnl_real: float, reason: str):
        icon = "🟢" if pnl_real >= 0 else "🔴"
        msg = (
            f"{icon} <b>POSICIÓN CERRADA</b>\n"
            f"Tipo: {signal}\n"
            f"Entrada: ${entry:,.2f} → Salida: ${exit_price:,.2f}\n"
            f"Lotes: {lots}\n"
            f"PnL real: ${pnl_real:+.4f}\n"
            f"Razón: {reason}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(msg)

    def send_daily_report(self, trade_log: list, pnl: float, regime: str):
        mode = CONFIG.get("runtime_mode", "paper").upper()
        if not trade_log:
            msg = (
                f"📊 <b>PORTFOLIO MASTER — Reporte Diario</b>\n"
                f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
                f"Sin trades ejecutados hoy.\n<i>Modo: {mode}</i>"
            )
        else:
            # We would need pandas here, but to avoid dependency in this module,
            # we can pass a precomputed summary or use a simple list.
            # For now, we'll assume trade_log is a list of dicts and we compute briefly.
            # However, to keep this module independent, we'll leave the computation to the caller.
            # Alternatively, we can import pandas here if we accept the dependency.
            # Let's import pandas conditionally or assume the caller has computed the summary.
            # Since the original code used pandas, we'll keep it and add pandas to the imports.
            try:
                import pandas as pd
                df  = pd.DataFrame(trade_log)
                buys  = (df['signal'] == 'BUY').sum()
                sells = (df['signal'] == 'SELL').sum()
                avg_iv = df['iv'].mean() if 'iv' in df.columns else 0
                last_p = df['price'].iloc[-1] if 'price' in df.columns else 0
                # PnL real si existe
                real_pnl = df['pnl_real'].sum() if 'pnl_real' in df.columns else pnl
                wins  = (df['pnl_real'] > 0).sum() if 'pnl_real' in df.columns else 0
                losses = (df['pnl_real'] < 0).sum() if 'pnl_real' in df.columns else 0
                winrate = wins/(wins+losses)*100 if (wins+losses) > 0 else 0
                pnl_icon    = "🟢" if real_pnl >= 0 else "🔴"
                regime_icon = {"bull":"🐂","bear":"🐻","sideways":"😴"}.get(regime,"❓")
                balance = CONFIG['capital'] + real_pnl
                msg = (
                    f"📊 <b>PORTFOLIO MASTER — Reporte Diario</b>\n"
                    f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
                    f"<b>💰 Capital:</b> ${CONFIG['capital']:.2f}\n"
                    f"<b>💼 Balance:</b> ${balance:.4f}\n"
                    f"<b>{pnl_icon} PnL real:</b> ${real_pnl:+.4f}\n\n"
                    f"<b>📈 Trades hoy:</b> {len(df)}\n"
                    f"  • 🟢 BUY:  {buys}\n"
                    f"  • 🔴 SELL: {sells}\n"
                    f"  • ✅ Wins: {wins} | ❌ Losses: {losses}\n"
                    f"  • 🎯 Win rate: {winrate:.1f}%\n\n"
                    f"<b>{regime_icon} Régimen actual:</b> {regime.upper()}\n"
                    f"<b>📏 IV promedio:</b> {avg_iv:.1%}\n"
                    f"<b>💲 Último precio BTC:</b> ${last_p:,.2f}\n\n"
                    f"<b>🤖 Bots activos:</b>\n"
                    f"  ✅ HMM Regime Detection\n"
                    f"  ✅ RandomForest Vol Surface\n"
                    f"  ✅ Black-Scholes Delta-Gamma\n\n"
                    f"<i>Modo: {mode}</i>"
                )
            except ImportError:
                # Fallback if pandas is not available
                msg = (
                    f"📊 <b>PORTFOLIO MASTER — Reporte Diario</b>\n"
                    f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
                    f"<b>💰 Capital:</b> ${CONFIG['capital']:.2f}\n"
                    f"<b>💼 Balance:</b> ${CONFIG['capital'] + pnl:.4f}\n"
                    f"<b>📈 PnL real:</b> ${pnl:+.4f}\n\n"
                    f"<b>📈 Trades hoy:</b> {len(trade_log)}\n"
                    f"<i>Modo: {mode}</i>\n"
                    f"<i>Nota: Requiere pandas para reporte detallado.</i>"
                )
        self.send(msg)

    def send_error(self, error: str):
        msg = f"⚠️ <b>ERROR EN BOT</b>\n{error}\n⏰ {datetime.now().strftime('%H:%M:%S')}"
        self.send(msg)