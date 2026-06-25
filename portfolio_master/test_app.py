import streamlit as st
st.set_page_config(page_title="Test App", page_icon="🧪")
st.title("Test App - Sin Datos Ni Gráficos")
st.write("Esta es una aplicación de prueba para descartar errores de dependencias.")
if st.button("Recargar"):
    st.rerun()
