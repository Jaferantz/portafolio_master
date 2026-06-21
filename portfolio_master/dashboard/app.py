import streamlit as st
import json
import pandas as pd
from pathlib import Path
import time
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración de la página
st.set_page_config(
    page_title="Portfolio Master v3.0 - Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ruta del archivo de estado (mismo que en el orquestador)
STATE_FILE = Path(__file__).parent.parent / "dashboard_state.json"

# Función para leer el estado de forma segura
def load_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {}
    except Exception as e:
        st.error(f"Error leyendo estado: {e}")
        return {}

# Título principal
st.title("📊 PORTFOLIO MASTER v3.0 - Dashboard en Tiempo Real")
st.caption(f"Actualizando cada 5 segundos • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Placeholder para métricas (se actualizarán en tiempo real)
placeholder = st.empty()

# Loop principal del dashboard
while True:
    state = load_state()

    if not state:
        with placeholder.container():
            st.warning("Esperando datos del sistema de trading...")
        time.sleep(5)
        continue

    # --- MÉTRICAS PRINCIPALES ---
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="💰 Balance Total",
            value=f"${state.get('balance', 0):,.2f}",
            delta=f"${state.get('pnl', 0):+,.2f}"
        )

    with col2:
        regime = state.get('regime', 'N/A').upper()
        regime_emoji = {"BULL": "🐂", "BEAR": "🐻", "SIDEWAYS": "😴"}.get(regime, "❓")
        st.metric(
            label="🧭 Régimen de Mercado",
            value=f"{regime_emoji} {regime}",
            delta=f"Conf: {state.get('conf', 0):.0%}" if 'conf' in state else None
        )

    with col3:
        st.metric(
            label="📈 Precio BTC",
            value=f"${state.get('price', 0):,.2f}"
        )

    with col4:
        signal = state.get('signal', 'NONE')
        signal_color = "green" if signal == "BUY" else "red" if signal == "SELL" else "gray"
        st.metric(
            label="🎯 Señal Actual",
            value=f"::<span style='color:{signal_color}'>{signal}</span>",
            help="Delta: {:.4f} | Gamma: {:.6f}".format(
                state.get('delta', 0), state.get('gamma', 0)
            )
        )

    # --- DETALLES DE POSICIÓN ---
    st.subheader("📌 Posición Abierta")
    if state.get('has_position') and state.get('position_details'):
        pos = state['position_details']
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Tipo", pos['signal'])
        with col2:
            st.metric("Entrada", f"${pos['entry']:,.2f}")
        with col3:
            st.metric("Tamaño", f"{pos['lots']:.5f} BTC")
        with col4:
            st.metric("SL / TP", f"${pos['sl']:,.2f} / ${pos['tp']:,.2f}")

        # PnL no realizado
        unrealized = pos.get('unrealized_pnl', 0)
        st.metric(
            label="💹 PnL No Realizado",
            value=f"${unrealized:+,.4f}",
            delta_color="normal" if unrealized >= 0 else "inverse"
        )
    else:
        st.info("No hay posición abierta actualmente")

    # --- INDICADORES TÉCNICOS ---
    st.subheader("📊 Indicadores del Mercado")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📏 Volatilidad Implícita (IV)", f"{state.get('iv', 0):.1%}")
    with col2:
        st.metric("📊 Order Flow Imbalance (OFI)", f"{state.get('ofi', 0):+.4f}")
    with col3:
        st.metric("💹 Pressure (Trades)", f"{state.get('pressure', 0):+.4f}")
    with col4:
        st.metric("📈 Tendencia EMA", "ALCISTA ⬆" if state.get('trend') == 'up' else "BAJISTA ⬇")

    # --- GRÁFICO DE PRECIO Y SEÑALES (simulado con historial limitado) ---
    # Nota: Para un historial completo necesitaríamos almacenar más datos.
    # Aquí mostramos solo el punto actual como referencia.
    st.subheader("📈 Vista General")

    # Crear un gráfico simple con el precio actual y niveles de SL/TP si hay posición
    fig = go.Figure()

    # Línea de precio actual (solo un punto para referencia)
    fig.add_trace(go.Scatter(
        x=[state.get('timestamp', '')],
        y=[state.get('price', 0)],
        mode='markers',
        name='Precio Actual',
        marker=dict(size=10, color='blue')
    ))

    # Si hay posición, mostrar niveles de SL y TP
    if state.get('has_position') and state.get('position_details'):
        pos = state['position_details']
        fig.add_hline(y=pos['sl'], line_dash="dash", line_color="red",
                     annotation_text="SL", annotation_position="bottom right")
        fig.add_hline(y=pos['tp'], line_dash="dash", line_color="green",
                     annotation_text="TP", annotation_position="top right")

    fig.update_layout(
        title="Precio Actual con Niveles de SL/TP",
        xaxis_title="Hora",
        yaxis_title="Precio (USDT)",
        height=300,
        showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- LOG DE TRADING RECIENTE (si está disponible) ---
    # Para esto necesitaríamos leer trade_log.csv, pero lo dejamos como extensión futura
    with st.expander("📋 Ver Log de Trading Reciente"):
        try:
            log_path = Path(__file__).parent.parent / "trade_log.csv"
            if log_path.exists():
                df = pd.read_csv(log_path)
                # Mostrar últimas 5 operaciones
                st.dataframe(df.tail(5).iloc[::-1], use_container_width=True)
            else:
                st.info("Aún no hay operaciones registradas")
        except Exception as e:
            st.error(f"Error leyendo log: {e}")

    # Esperar antes de la próxima actualización
    time.sleep(5)