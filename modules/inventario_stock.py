import streamlit as st
import pandas as pd
import time

def render(get_connection):
    st.title("Gestión de Inventario (GHV - Service)")

    tab_inv1, tab_inv2 = st.tabs(
        ["📥 Cargar Producto", "📋 Stock Actual / Disponibilidad"]
    )

    with tab_inv1:
        st.subheader("Ingreso de Mercadería al Taller")
        with st.form("form_nuevo_producto", clear_on_submit=True):
            col_in1, col_in2 = st.columns(2)
            with col_in1:
                cat = st.selectbox("Categoría del Artículo:", [
                    "DISCO SSD",
                    "MEMORIA RAM",
                    "ADAPTADOR CADDY",
                    "FUENTES / CARGADORES",
                    "COOLERS",
                    "PANTALLAS",
                    "OTROS",
                ])
                mrc = st.text_input("Marca (Ej: Kingston, Crucial, WD)").upper().strip()
                cap = (
                    st.text_input(
                        "Capacidad / Especificación (Ej: 480GB SATA, 8GB DDR4 3200Mhz,"
                        " 9.5mm)"
                    )
                    .upper()
                    .strip()
                )
            with col_in2:
                cant_stock = st.number_input(
                    "Cantidad de Unidades Ingresantes:", min_value=1, step=1, value=1
                )
                p_costo = st.number_input(
                    "Precio de Costo Mayorista (Gs):",
                    min_value=0,
                    step=10000,
                    format="%d",
                )
                p_venta = st.number_input(
                    "Precio de Venta al Público Sugerido (Gs):",
                    min_value=0,
                    step=10000,
                    format="%d",
                )

            submit_p = st.form_submit_button("📥 Guardar en Inventario")

        if submit_p:
            if not mrc or not cap:
                st.error(
                    "⚠️ Debes completar la Marca y la Especificación/Capacidad del"
                    " producto."
                )
            else:
                try:
                    with get_connection() as conn_inv:
                        conn_inv.execute(
                            """
                                INSERT INTO productos (categoria, marca, capacidad_especificacion, stock, precio_costo, precio_venta, sincronizado)
                                VALUES (?, ?, ?, ?, ?, ?, 0)
                            """,
                            (cat, mrc, cap, cant_stock, p_costo, p_venta),
                        )
                        conn_inv.commit()
                    st.success(
                        f"✅ ¡{cat} {mrc} ({cap}) cargado correctamente al stock!"
                    )
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar producto: {e}")

    with tab_inv2:
        st.subheader("Inventario de Artículos Disponibles")
        try:
            with get_connection() as conn:
                df_stock = pd.read_sql_query(
                    """
                        SELECT id as ID, categoria as Categoría, marca as Marca, 
                               capacidad_especificacion as Detalle, stock as [Stock Disponible], 
                               precio_costo as [Precio_Costo], precio_venta as [Precio_Venta] 
                        FROM productos ORDER BY categoria ASC, marca ASC
                    """,
                    conn,
                )
        except Exception as e:
            st.error(f"Error al cargar inventario: {e}")
            df_stock = pd.DataFrame()

        if not df_stock.empty:
            df_stock_fmt = df_stock.copy()
            df_stock_fmt["Precio_Costo"] = df_stock_fmt["Precio_Costo"].apply(
                lambda x: (
                    f"{int(x):,}".replace(",", ".") if pd.notna(x) else "0"
                )
            )
            df_stock_fmt["Precio_Venta"] = df_stock_fmt["Precio_Venta"].apply(
                lambda x: (
                    f"{int(x):,}".replace(",", ".") if pd.notna(x) else "0"
                )
            )
            df_stock_fmt = df_stock_fmt.rename(
                columns={"Precio_Costo": "Costo (Gs)", "Precio_Venta": "P. Venta (Gs)"}
            )
            st.dataframe(df_stock_fmt, width="stretch", hide_index=True)

            st.markdown("---")
            st.subheader("📝 Editar Cualquier Dato de un Producto")

            opciones_prod = {
                f"ID {row['ID']} - {row['Categoría']} {row['Marca']} ({row['Detalle']})": row
                for _, row in df_stock.iterrows()
            }
            prod_seleccionado = st.selectbox(
                "Seleccione el producto que desea modificar por completo:",
                options=list(opciones_prod.keys()),
            )

            datos_prod_act = opciones_prod[prod_seleccionado]
            id_prod_editar = int(datos_prod_act["ID"])

            cats_permitidas = [
                "DISCO SSD",
                "MEMORIA RAM",
                "ADAPTADOR CADDY",
                "FUENTES / CARGADORES",
                "COOLERS",
                "PANTALLAS",
                "OTROS",
            ]
            cat_act = datos_prod_act["Categoría"]
            idx_cat = (
                cats_permitidas.index(cat_act) if cat_act in cats_permitidas else 0
            )

            val_mrc_def = (
                str(datos_prod_act["Marca"]) if pd.notna(datos_prod_act["Marca"]) else ""
            )
            val_det_def = (
                str(datos_prod_act["Detalle"])
                if pd.notna(datos_prod_act["Detalle"])
                else ""
            )
            val_stk_def = (
                int(datos_prod_act["Stock Disponible"])
                if pd.notna(datos_prod_act["Stock Disponible"])
                else 0
            )
            val_cst_def = (
                int(datos_prod_act["Precio_Costo"])
                if pd.notna(datos_prod_act["Precio_Costo"])
                else 0
            )
            val_vta_def = (
                int(datos_prod_act["Precio_Venta"])
                if pd.notna(datos_prod_act["Precio_Venta"])
                else 0
            )

            with st.form("form_edicion_total_producto"):
                col_ed_p1, col_ed_p2 = st.columns(2)
                with col_ed_p1:
                    n_cat = st.selectbox(
                        "Categoría:", options=cats_permitidas, index=idx_cat
                    )
                    n_marca = st.text_input("Marca:", value=val_mrc_def).upper().strip()
                    n_detalle = (
                        st.text_input("Detalle / Especificación:", value=val_det_def)
                        .upper()
                        .strip()
                    )
                with col_ed_p2:
                    n_stock = st.number_input(
                        "Cantidad en Stock:", min_value=0, value=val_stk_def
                    )
                    n_costo = st.number_input(
                        "Precio de Costo (Gs):",
                        min_value=0,
                        value=val_cst_def,
                        step=10000,
                    )
                    n_venta = st.number_input(
                        "Precio de Venta (Gs):",
                        min_value=0,
                        value=val_vta_def,
                        step=10000,
                    )

                btn_guardar_prod = st.form_submit_button(
                    "💾 Guardar Cambios del Producto"
                )

            if btn_guardar_prod:
                if not n_marca or not n_detalle:
                    st.error("⚠️ La marca y el detalle no pueden quedar vacíos.")
                else:
                    try:
                        with get_connection() as conn_prod_up:
                            conn_prod_up.execute(
                                """
                                    UPDATE productos 
                                    SET categoria = ?, marca = ?, capacidad_especificacion = ?, stock = ?, precio_costo = ?, precio_venta = ?, sincronizado = 0
                                    WHERE id = ?
                                """,
                                (
                                    n_cat,
                                    n_marca,
                                    n_detalle,
                                    n_stock,
                                    n_costo,
                                    n_venta,
                                    id_prod_editar,
                                ),
                            )
                            conn_prod_up.commit()
                        st.success(
                            f"✅ ¡Producto ID {id_prod_editar} modificado exitosamente!"
                        )
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al actualizar el inventario: {e}")

            st.markdown("---")
            pop_eliminar_prod = st.popover("🗑️ Eliminar Producto del Inventario")
            with pop_eliminar_prod:
                st.warning(
                    "¿Estás seguro de que querés borrar permanentemente el ID"
                    f" {id_prod_editar}?"
                )
                if st.button(
                    "Sí, borrar del stock permanentemente",
                    key=f"del_prod_inv_{id_prod_editar}",
                ):
                    with get_connection() as conn_prod_del:
                        conn_prod_del.execute(
                            "DELETE FROM productos WHERE id = ?", (id_prod_editar,)
                        )
                        conn_prod_del.commit()
                    st.error("Producto eliminado del inventario.")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("El inventario está vacío actualmente.")