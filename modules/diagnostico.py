import pandas as pd
import streamlit as st
from modules.database import get_connection  # Importa la conexión híbrida centralizada

# --- CÓDIGO DE DIAGNÓSTICO DINÁMICO ---
with st.expander("🔍 Herramienta de Inspección de OT (Diagnóstico)"):
    # Permite buscar cualquier OT introduciendo el número
    ot_buscada = st.number_input("Ingresá el ID de la OT a consultar:", min_value=1, value=1, step=1)
    
    try:
        # Usa la función centralizada para conectar (local o Turso)
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                p.id AS [ID Pago], 
                p.orden_id AS [OT #], 
                p.monto_cuota AS [Monto], 
                p.fecha_vencimiento AS [Vencimiento],
                p.estado_pago AS [Estado Pago], 
                p.notas AS [Notas / Concepto],
                o.estado AS [Estado Orden],
                o.descripcion AS [Detalle Trabajo]
            FROM pagos p
            JOIN ordenes o ON p.orden_id = o.id
            WHERE p.orden_id = ?
        """
        
        cursor.execute(query, (ot_buscada,))
        rows = cursor.fetchall()
        
        # Extraemos las columnas de manera dinámica y armamos el DataFrame
        column_names = [desc[0] for desc in cursor.description] if cursor.description else []
        test_query = pd.DataFrame(rows, columns=column_names)
        
        conn.close()
        
        if not test_query.empty:
            st.success(f"Se encontraron {len(test_query)} registro(s) para la OT #{ot_buscada}:")
            
            # Formatear el monto para visualización rápida
            test_query['Monto'] = test_query['Monto'].apply(lambda x: f"{int(x):,} Gs.".replace(",", "."))
            st.dataframe(test_query, use_container_width=True, hide_index=True)
        else:
            st.warning(f"⚠️ No se encontraron pagos vinculados a la OT #{ot_buscada} en la tabla 'ordenes/pagos'.")

    except Exception as e:
        st.error(f"❌ Error al consultar la base de datos: {e}")