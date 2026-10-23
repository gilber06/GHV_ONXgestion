import streamlit as st
import pandas as pd
import time

def render(get_connection):
    st.title("Registro Histórico y Auditoría de Pagos")

    # Checkbox para alternar entre ver solo pagados o todos los registros (Modo Auditoría)
    ver_todos = st.checkbox("🔍 Modo Auditoría: Mostrar todos los estados (Pendiente, Pagado, etc.)", value=True)

    try:
        with get_connection() as conn:
            if ver_todos:
                query = """
                    SELECT p.id as ID, 
                           p.fecha_vencimiento as Fecha, 
                           COALESCE(n.nombre, 'GHV-Service') as Negocio, 
                           COALESCE(c.nombre, 'Sin Asignar') as Cliente, 
                           COALESCE(NULLIF(c.apodo, ''), c.nombre, 'Sin Empresa') as Empresa, 
                           p.monto_cuota as Monto,
                           p.estado as Estado
                    FROM pagos p 
                    LEFT JOIN ordenes o ON p.orden_id = o.id 
                    LEFT JOIN clientes c ON o.cliente_id = c.id
                    LEFT JOIN negocios n ON o.negocio_id = n.id 
                    ORDER BY p.id DESC
                """
            else:
                query = """
                    SELECT p.id as ID, 
                           p.fecha_vencimiento as Fecha, 
                           COALESCE(n.nombre, 'GHV-Service') as Negocio, 
                           COALESCE(c.nombre, 'Sin Asignar') as Cliente, 
                           COALESCE(NULLIF(c.apodo, ''), c.nombre, 'Sin Empresa') as Empresa, 
                           p.monto_cuota as Monto,
                           p.estado as Estado
                    FROM pagos p 
                    LEFT JOIN ordenes o ON p.orden_id = o.id 
                    LEFT JOIN clientes c ON o.cliente_id = c.id
                    LEFT JOIN negocios n ON o.negocio_id = n.id 
                    WHERE LOWER(TRIM(p.estado)) = 'pagado' 
                    ORDER BY p.id DESC
                """
            df_h = pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        df_h = pd.DataFrame()

    if not df_h.empty:
        df_display = df_h.copy()
        df_display["Monto"] = df_display["Monto"].apply(
            lambda x: f"{int(x):,} Gs.".replace(",", ".") if pd.notnull(x) else "0 Gs."
        )
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("↩️ Gestión / Reversión de Pagos")

        c_rev1, c_rev2 = st.columns([2, 1])
        with c_rev1:
            id_pago_sel = st.selectbox(
                "Seleccioná el ID del pago a gestionar:",
                options=df_h["ID"],
            )
            r_sel = df_h[df_h["ID"] == id_pago_sel].iloc[0]
            st.info(
                f"Seleccionado: **ID #{r_sel['ID']}** - {r_sel['Cliente']}"
                f" ({r_sel['Empresa']}) | Estado actual: **{r_sel['Estado']}** | Monto: **{r_sel['Monto']}**"
            )

        with c_rev2:
            st.write("")
            st.write("")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("🔄 Marcar Pendiente", use_container_width=True):
                    try:
                        with get_connection() as conn_rev:
                            conn_rev.execute(
                                "UPDATE pagos SET estado = 'Pendiente' WHERE id = ?",
                                (int(id_pago_sel),),
                            )
                            conn_rev.commit()
                        st.success(f"✅ El pago ID #{id_pago_sel} pasó a 'Pendiente'.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            with col_b2:
                if st.button("✅ Marcar Pagado", use_container_width=True):
                    try:
                        with get_connection() as conn_rev:
                            conn_rev.execute(
                                "UPDATE pagos SET estado = 'Pagado' WHERE id = ?",
                                (int(id_pago_sel),),
                            )
                            conn_rev.commit()
                        st.success(f"✅ El pago ID #{id_pago_sel} pasó a 'Pagado'.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        st.info("No hay registros en la base de datos.")