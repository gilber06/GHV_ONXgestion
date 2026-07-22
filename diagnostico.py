# --- CÓDIGO DE DIAGNÓSTICO ---
st.write("### 🔍 Buscando la OT 1 en la Base de Datos...")
test_query = pd.read_sql_query("""
    SELECT p.id, p.orden_id, p.monto_cuota, p.estado_pago, o.estado 
    FROM pagos p
    JOIN ordenes o ON p.orden_id = o.id
    WHERE p.orden_id = 1
""", conn)
st.write(test_query)