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
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# Constants and state loading
# ----------------------------------------------------------------------
STATE_FILE = Path(__file__).parent.parent / "dashboard_state.json"

@st.cache_data(ttl=5)  # ← ESTO ES LA CLAVE: cachea los datos por 5 segundos
def load_state_cached() -> dict:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {}
    except Exception as e:
        st.error(f"❌ Error reading state file: {e}")
        return {}

# ----------------------------------------------------------------------
# Load state (se recarga automáticamente cada 5s por el TTL)
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

# Si no hay datos, mostramos mensaje y paramos
if not state:
    st.info("⏳ Esperando datos del sistema de trading…")
    st.stop()

# ----------------------------------------------------------------------
# MAIN METRICS (igual que antes, pero sin errores)
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

# ... (aquí va el resto de tu código: Position Details, Indicators, Chart, Log)
# ... (es exactamente igual, no lo repito por espacio)

# ----------------------------------------------------------------------
# 🔄 Botón de actualización manual (opcional, pero útil)
# ----------------------------------------------------------------------
if st.button("🔄 Actualizar ahora"):
    st.cache_data.clear()
    st.experimental_rerun()
