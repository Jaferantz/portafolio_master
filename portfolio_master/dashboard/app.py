este es mi codigo actual no cambiaste nada importante?                                                                                                                                     import streamlit as st
import json
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go
from datetime import datetime

# ----------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Portfolio Master v3.0 - Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
STATE_FILE = Path(__file__).parent.parent / "dashboard_state.json"
REFRESH_INTERVAL_MS = 5_000  # 5 seconds → matches your original sleep(5)

# ----------------------------------------------------------------------
# Helper: read state safely
# ----------------------------------------------------------------------
def load_state() -> dict:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {}
    except Exception as e:
        st.error(f"❌ Error reading state file: {e}")
        return {}

# ----------------------------------------------------------------------
# Load latest state
# ----------------------------------------------------------------------
state = load_state()

# ----------------------------------------------------------------------
# Title & caption
# ----------------------------------------------------------------------
st.title("📊 PORTFOLIO MASTER v3.0 - Dashboard en Tiempo Real")
st.caption(
    f"Actualizando cada {REFRESH_INTERVAL_MS/1000:.0f} s • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

# ----------------------------------------------------------------------
# If no state yet, show a friendly message and stop execution
# ----------------------------------------------------------------------
if not state:
    st.info("⏳ Esperando datos del sistema de trading…")
    st.stop()  # prevents the rest of the script from running on empty state

# ----------------------------------------------------------------------
# MAIN METRICS
# ----------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        label="💰 Balance Total",
        value=f"${state.get('balance', 0):,.2f}",
        delta=f"${state.get('pnl', 0):+,.2f}",
    )

with c2:
    regime = state.get("regime", "N/A").upper()
    regime_emoji = {"BULL": "🐂", "BEAR": "🐻", "SIDEWAYS": "😴"}.get(regime, "❓")
    st.metric(
        label="🧭 Régimen de Mercado",
        value=f"{regime_emoji} {regime}",
        delta=(
            f"Conf: {state.get('conf', 0):.0%}"
            if "conf" in state
            else None
        ),
    )

with c3:
    st.metric(label="📈 Precio BTC", value=f"${state.get('price', 0):,.2f}")

with c4:
    signal = state.get("signal", "NONE")
    signal_color = (
        "green"
        if signal == "BUY"
        else "red"
        if signal == "SELL"
        else "gray"
    )
    st.metric(
        label="🎯 Señal Actual",
        value=f"::<span style='color:{signal_color}'>{signal}</span>",
        help=(
            "Delta: {:.4f} | Gamma: {:.6f}".format(
                state.get("delta", 0), state.get("gamma", 0)
            )
        ),
    )

# ----------------------------------------------------------------------
# POSITION DETAILS
# ----------------------------------------------------------------------
st.subheader("📌 Posición Abierta")
if state.get("has_position") and state.get("position_details"):
    pos = state["position_details"]
    pc1, pc2, pc3, pc4 = st.columns(4)

    with pc1:
        st.metric("Tipo", pos["signal"])
    with pc2:
        st.metric("Entrada", f"${pos['entry']:,.2f}")
    with pc3:
        st.metric("Tamaño", f"{pos['lots']:.5f} BTC")
    with pc4:
        st.metric("SL / TP", f"${pos['sl']:,.2f} / ${pos['tp']:,.2f}")

    unrealized = pos.get("unrealized_pnl", 0)
    st.metric(
        label="💹 PnL No Realizado",
        value=f"${unrealized:+,.4f}",
        delta_color="normal" if unrealized >= 0 else "inverse",
    )
else:
    st.info("No hay posición abierta actualmente")

# ----------------------------------------------------------------------
# TECHNICAL INDICATORS
# ----------------------------------------------------------------------
st.subheader("📊 Indicadores del Mercado")
ti1, ti2, ti3, ti4 = st.columns(4)

with ti1:
    st.metric("📏 Volatilidad Implícita (IV)", f"{state.get('iv', 0):.1%}")
with ti2:
    st.metric("📊 Order Flow Imbalance (OFI)", f"{state.get('ofi', 0):+.4f}")
with ti3:
    st.metric("💹 Pressure (Trades)", f"{state.get('pressure', 0):+.4f}")
with ti4:
    st.metric(
        label="📈 Tendencia EMA",
        value="ALCISTA ⬆" if state.get("trend") == "up" else "BAJISTA ⬇",
    )

# ----------------------------------------------------------------------
# PRICE CHART (current price + SL/TP if a position exists)
# ----------------------------------------------------------------------
st.subheader("📈 Vista General")
fig = go.Figure()

# Current price as a single marker
fig.add_trace(
    go.Scatter(
        x=[state.get("timestamp", "")],
        y=[state.get("price", 0)],
        mode="markers",
        name="Precio Actual",
        marker=dict(size=10, color="blue"),
    )
)

# Add SL/TP lines when a position is open
if state.get("has_position") and state.get("position_details"):
    pos = state["position_details"]
    fig.add_hline(
        y=pos["sl"],
        line_dash="dash",
        line_color="red",
        annotation_text="SL",
        annotation_position="bottom right",
    )
    fig.add_hline(
        y=pos["tp"],
        line_dash="dash",
        line_color="green",
        annotation_text="TP",
        annotation_position="top right",
    )

fig.update_layout(
    title="Precio Actual con Niveles de SL/TP",
    xaxis_title="Hora",
    yaxis_title="Precio (USDT)",
    height=300,
    showlegend=True,
)

st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# RECENT TRADE LOG (optional)
# ----------------------------------------------------------------------
with st.expander("📋 Ver Log de Trading Reciente"):
    try:
        log_path = Path(__file__).parent.parent / "trade_log.csv"
        if log_path.exists():
            df = pd.read_csv(log_path)
            # show the last 5 rows, newest on top
            st.dataframe(df.tail(5).iloc[::-1], use_container_width=True)
        else:
            st.info("Aún no hay operaciones registradas")
    except Exception as e:
        st.error(f"Error leyendo el log: {e}")
# ----------------------------------------------------------------------
# AUTO-RECARGA CON MÉTODO NATIVO DE STREAMLIT
# ----------------------------------------------------------------------
import time
time.sleep(5)
st.experimental_rerun()

# ----------------------------------------------------------------------
# End of script – Streamlit will now wait REFRESH_INTERVAL_MS and rerun
