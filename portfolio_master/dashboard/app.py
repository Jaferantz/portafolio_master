import streamlit as st
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
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",  # Nota: era "initial_slider_state", corregido a "initial_sidebar_state"
)

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
STATE_FILE = Path(__file__).parent.parent / "dashboard_state.json"

# ----------------------------------------------------------------------
# Helper: read state safely con CACHE y TTL
# ----------------------------------------------------------------------
@st.cache_data(ttl=5)  # Recarga los datos cada 5 segundos
def load_state_cached() -> dict:
    """Carga el estado del archivo JSON con caché de 5 segundos."""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        st.error(f"❌ Error reading state file: {e}")
        return {}

# ----------------------------------------------------------------------
# Load latest state (se recarga automáticamente cada 5s por el TTL)
# ----------------------------------------------------------------------
state = load_state_cached()

# ----------------------------------------------------------------------
# Title & caption
# ----------------------------------------------------------------------
st.title("📊 PORTFOLIO MASTER v3.0 - Dashboard en Tiempo Real")
st.caption(
    f"Actualizando cada 5 s • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

# ----------------------------------------------------------------------
# If no state yet, show a friendly message and stop execution
# ----------------------------------------------------------------------
if not state:
    st.info("⏳ Esperando datos del sistema de trading…")
    st.stop()

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
        delta=f"Conf: {state.get('conf', 0):.0%}" if "conf" in state else None,
    )

with c3:
    st.metric(label="📈 Precio BTC", value=f"${state.get('price', 0):,.2f}")

with c4:
    signal = state.get("signal", "NONE")
    st.metric(
        label="🎯 Señal Actual",
        value=signal,
        help=f"Delta: {state.get('delta', 0):.4f} | Gamma: {state.get('gamma', 0):.6f}",
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
# PRICE CHART
# ----------------------------------------------------------------------
st.subheader("📈 Vista General")
fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=[state.get("timestamp", "")],
        y=[state.get("price", 0)],
        mode="markers",
        name="Precio Actual",
        marker=dict(size=10, color="blue"),
    )
)

if state.get("has_position") and state.get("position_details"):
    pos = state["position_details"]
    fig.add_hline(y=pos["sl"], line_dash="dash", line_color="red", annotation_text="SL")
    fig.add_hline(y=pos["tp"], line_dash="dash", line_color="green", annotation_text="TP")

fig.update_layout(
    title="Precio Actual con Niveles de SL/TP",
    xaxis_title="Hora",
    yaxis_title="Precio (USDT)",
    height=300,
    showlegend=True,
)

st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# RECENT TRADE LOG
# ----------------------------------------------------------------------
with st.expander("📋 Ver Log de Trading Reciente"):
    try:
        log_path = Path(__file__).parent.parent / "trade_log.csv"
        if log_path.exists():
            df = pd.read_csv(log_path)
            st.dataframe(df.tail(5).iloc[::-1], use_container_width=True)
        else:
            st.info("Aún no hay operaciones registradas")
    except Exception as e:
        st.error(f"Error leyendo el log: {e}")

# ----------------------------------------------------------------------
# Botón para forzar actualización manual (opcional)
# ----------------------------------------------------------------------
if st.button("🔄 Forzar actualización ahora"):
    st.cache_data.clear()
    st.rerun()
