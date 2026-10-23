import streamlit as st
import pandas as pd
import plotly.express as px

def render(get_connection):
    st.header("📊 Reportes y Análisis de Negocio")
    tab_r1, tab_r2 = st.tabs(
        ["Rentabilidad por Negocio", "Comportamiento de Cliente"]
    )

    with tab_r1:
        st.subheader("Análisis de Margen Real")

        try:
            with get_connection() as conn:
                df_rent = pd.read_sql_query(
                    """
                        SELECT 
                            n.nombre as Negocio,
                            COALESCE((
                                SELECT SUM(p.monto_cuota) 
                                FROM pagos p 
                                JOIN ordenes o2 ON p.orden_id = o2.id 
                                WHERE o2.negocio_id = n.id
                            ), 0) as Ingresos_Totales,
                            COALESCE((
                                SELECT SUM(o3.costo_insumos) 
                                FROM ordenes o3 
                                WHERE o3.negocio_id = n.id
                            ), 0) as Costos_Totales
                        FROM negocios n
                    """,
                    conn,
                )
        except Exception as e:
            st.error(f"Error al cargar la rentabilidad: {e}")
            df_rent = pd.DataFrame()

        if not df_rent.empty:
            df_rent["Utilidad_Neta"] = (
                df_rent["Ingresos_Totales"] - df_rent["Costos_Totales"]
            )
            col_graf, col_tabla = st.columns([1, 1])

            with col_graf:
                if df_rent["Utilidad_Neta"].sum() > 0:
                    fig_rent = px.pie(
                        df_rent,
                        values="Utilidad_Neta",
                        names="Negocio",
                        title="Distribución de Utilidad Neta",
                        hole=0.4,
                        color_discrete_sequence=["#3498db", "#e67e22"],
                    )
                    st.plotly_chart(fig_rent, use_container_width=True)
                else:
                    st.warning("La utilidad total es 0 o negativa para graficar.")

            with col_tabla:
                df_visual = df_rent.copy()

                def pts(x):
                    return f"{int(x):,}".replace(",", ".")

                df_visual["Ingresos_Totales"] = df_visual["Ingresos_Totales"].apply(pts)
                df_visual["Costos_Totales"] = df_visual["Costos_Totales"].apply(pts)
                df_visual["Utilidad_Neta"] = df_visual["Utilidad_Neta"].apply(pts)
                st.table(df_visual)
        else:
            st.info("No hay datos de rentabilidad disponibles.")

    with tab_r2:
        st.subheader("Análisis de Comportamiento por Cliente")

        try:
            with get_connection() as conn:
                df_comp = pd.read_sql_query(
                    """
                        SELECT 
                            c.apodo as Empresa,
                            COUNT(DISTINCT o.id) as Cantidad_OTs,
                            SUM(o.monto_total) as Volumen_Contratado,
                            COALESCE((
                                SELECT SUM(p.monto_cuota) 
                                FROM pagos p 
                                JOIN ordenes o2 ON p.orden_id = o2.id 
                                WHERE o2.cliente_id = c.id AND p.estado = 'Pagado'
                            ), 0) as Total_Pagado,
                            COALESCE((
                                SELECT SUM(p.monto_cuota) 
                                FROM pagos p 
                                JOIN ordenes o2 ON p.orden_id = o2.id 
                                WHERE o2.cliente_id = c.id AND p.estado = 'Pendiente'
                            ), 0) as Saldo_Pendiente
                        FROM clientes c
                        JOIN ordenes o ON c.id = o.cliente_id
                        GROUP BY c.apodo
                        ORDER BY Volumen_Contratado DESC
                    """,
                    conn,
                )
        except Exception as e:
            st.error(f"Error al cargar comportamiento de clientes: {e}")
            df_comp = pd.DataFrame()

        if not df_comp.empty:
            fig_bar = px.bar(
                df_comp,
                x="Empresa",
                y=["Total_Pagado", "Saldo_Pendiente"],
                title="Saldos Reales por Cliente",
                barmode="stack",
                color_discrete_map={
                    "Total_Pagado": "#2ecc71",
                    "Saldo_Pendiente": "#e74c3c",
                },
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            df_comp_fmt = df_comp.copy()
            for col in ["Volumen_Contratado", "Total_Pagado", "Saldo_Pendiente"]:
                df_comp_fmt[col] = df_comp_fmt[col].apply(
                    lambda x: f"{int(x):,}".replace(",", ".")
                )
            st.dataframe(df_comp_fmt, use_container_width=True)
        else:
            st.info("No hay datos de comportamiento por cliente disponibles.")