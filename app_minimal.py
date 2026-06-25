import streamlit as st

st.set_page_config(page_title="Test", page_icon="🧪")

st.title("🧪 TEST - APLICACIÓN MÍNIMA")
st.write("Si ves esto sin errores, el problema está en tu código original.")

if st.button("🔄 Recargar"):
    st.rerun()

st.caption("Esta app solo existe para diagnosticar el error 'removeChild'.")
