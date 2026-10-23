import streamlit as st
import pandas as pd
import time
from datetime import datetime
import urllib.parse
from dateutil.relativedelta import relativedelta

def render(get_connection):
    try:
        # Bloque de seguridad: Asegura que las tablas y columnas necesarias existan en la BD histórica
        with get_connection() as conn_init:
            cur_init = conn_init.cursor()
            cur_init.execute("""
                CREATE TABLE IF NOT EXISTS pagos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    orden_id INTEGER,
                    monto_cuota REAL DEFAULT 0,
                    fecha_vencimiento TEXT,
                    estado TEXT DEFAULT 'Pendiente',
                    notas TEXT
                )
            """)
            cur_init.execute("""
                CREATE TABLE IF NOT EXISTS negocios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT
                )
            """)
            try:
                cur_init.execute("ALTER TABLE clientes ADD COLUMN apodo TEXT;")
            except Exception:
                pass
            try:
                cur_init.execute("ALTER TABLE ordenes ADD COLUMN negocio_id INTEGER;")
            except Exception:
                pass
            try:
                cur_init.execute("ALTER TABLE ordenes ADD COLUMN descripcion TEXT;")
            except Exception:
                pass
            conn_init.commit()

        st.title("Control de Cobros")
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT p.id as ID,
                   COALESCE(n.nombre, 'Sin Negocio') as Negocio,
                   COALESCE(NULLIF(c.apodo, ''), c.nombre, 'Sin Cliente') as Empresa,
                   COALESCE(c.nombre, 'Sin Contacto') as Contacto,
                   p.monto_cuota as Monto,
                   p.fecha_vencimiento as Vence,
                   COALESCE(o.descripcion, 'Sin Detalle') as Detalle,
                   COALESCE(c.telefono, '') as Telefono,
                   COALESCE(p.notas, '') as Notas
            FROM pagos p
            LEFT JOIN ordenes o ON p.orden_id = o.id
            LEFT JOIN clientes c ON o.cliente_id = c.id
            LEFT JOIN negocios n ON o.negocio_id = n.id
            WHERE LOWER(TRIM(p.estado)) = 'pendiente'
            ORDER BY p.fecha_vencimiento ASC
            """
        )
        rows = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]
        df_p = pd.DataFrame(rows, columns=column_names)

        if not df_p.empty:
            clientes_con_deuda = df_p["Empresa"].unique()
            hoy_str = datetime.now().strftime("%Y-%m-%d")

            for empresa in clientes_con_deuda:
                pagos_cliente = df_p[df_p["Empresa"] == empresa]
                total_deuda_cliente = pagos_cliente["Monto"].sum()

                # Verificar si el cliente tiene alguna cuota vencida
                tiene_vencidos = any(pagos_cliente["Vence"] < hoy_str)
                
                prefijo = "🔴 [VENCIDO] " if tiene_vencidos else "👤 "
                expander_label = f"{prefijo}{empresa} - (Total Pendiente: {int(total_deuda_cliente):,}".replace(",", ".") + " Gs.)"

                with st.expander(expander_label):
                    if tiene_vencidos:
                        st.markdown(
                            """
                            <div style="background-color: #ffe6e6; border-left: 5px solid #ff4d4d; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                                <strong style="color: #cc0000;">⚠️ Atención:</strong> Este cliente posee una o más órdenes/cuotas vencidas. Revisa las filas resaltadas en rojo en la tabla.
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    pagos_vista = pagos_cliente.copy()
                    pagos_vista["Notas"] = pagos_vista["Notas"].fillna("")
                    
                    # Columna de estado individual por fila
                    pagos_vista["Estado"] = pagos_vista["Vence"].apply(
                        lambda x: "🔴 VENCIDO" if str(x) < hoy_str else "🟢 Al día"
                    )
                    
                    pagos_vista["Monto"] = pagos_vista["Monto"].apply(lambda x: f"{int(x):,} Gs.".replace(",", "."))

                    # Función para aplicar estilo de fila si está vencida
                    def resaltar_filas_vencidas(row):
                        if str(row['Vence']) < hoy_str:
                            return ['background-color: #ffe6e6; color: #cc0000; font-weight: bold;'] * len(row)
                        return [''] * len(row)

                    df_mostrar = pagos_vista[["ID", "Estado", "Vence", "Monto", "Detalle", "Notas"]]
                    
                    st.dataframe(
                        df_mostrar.style.apply(resaltar_filas_vencidas, axis=1),
                        use_container_width=True,
                        hide_index=True
                    )

                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        pago_id = st.selectbox(
                            f"ID a gestionar ({empresa}):",
                            pagos_cliente["ID"],
                            key=f"sel_{empresa}",
                        )

                        tab_pago1, tab_pago2, tab_pago3 = st.tabs(
                            ["✅ Cobrar", "📅 Mover Fecha", "✂️ Dividir en Cuotas"]
                        )

                        with tab_pago1:
                            if st.button(
                                f"Confirmar Cobro ID {pago_id}",
                                key=f"btn_cobrar_{empresa}_{pago_id}",
                            ):
                                conn.execute(
                                    "UPDATE pagos SET estado = 'Pagado' WHERE id = ?",
                                    (pago_id,),
                                )
                                conn.commit()
                                st.success("¡Pago marcado como Pagado!")
                                time.sleep(1)
                                st.rerun()

                        with tab_pago2:
                            nueva_fecha = st.date_input(
                                "Mover a:", key=f"f_{empresa}_{pago_id}"
                            )
                            nota_reprog = st.text_input(
                                "Motivo:",
                                placeholder="Ej: Pidió prórroga",
                                key=f"n_{empresa}_{pago_id}",
                            )
                            if st.button(
                                "Guardar Nueva Fecha", key=f"btn_reprog_{empresa}_{pago_id}"
                            ):
                                with get_connection() as conn_reprog:
                                    conn_reprog.execute(
                                        """
                                        UPDATE pagos 
                                        SET fecha_vencimiento = ? 
                                        WHERE id = ?
                                    """,
                                        (
                                            nueva_fecha.strftime("%Y-%m-%d"),
                                            pago_id,
                                        ),
                                    )
                                    conn_reprog.commit()
                                st.success(f"Vencimiento movido al {nueva_fecha}")
                                time.sleep(1)
                                st.rerun()

                        with tab_pago3:
                            num_partes = st.number_input(
                                "Dividir en cuántas cuotas:",
                                min_value=2,
                                max_value=12,
                                value=2,
                                key=f"div_num_{empresa}_{pago_id}",
                            )
                            fecha_primera = st.date_input(
                                "Fecha 1ª cuota:",
                                value=datetime.now().date(),
                                key=f"div_f_{empresa}_{pago_id}",
                            )

                            match_monto = pagos_cliente[pagos_cliente["ID"] == pago_id]
                            monto_actual_pago = match_monto["Monto"].values[0] if not match_monto.empty else 0
                            monto_nueva_cuota = monto_actual_pago / num_partes
                            st.caption(
                                f"💡 Se generarán **{num_partes} cuotas de"
                                f" {int(monto_nueva_cuota):,} Gs.**".replace(",", ".")
                            )

                            if st.button(
                                "✂️ Confirmar División de Pago",
                                key=f"btn_dividir_{empresa}_{pago_id}",
                            ):
                                with get_connection() as conn_div:
                                    cursor_div = conn_div.cursor()
                                    cursor_div.execute(
                                        "SELECT orden_id, notas FROM pagos WHERE id = ?", (pago_id,)
                                    )
                                    res_div = cursor_div.fetchone()
                                    ord_id = res_div[0] if res_div else None
                                    nota_orig = res_div[1] if res_div and len(res_div) > 1 else None
                                    nota_orig_txt = nota_orig if nota_orig else "CUOTA"

                                    cursor_div.execute("DELETE FROM pagos WHERE id = ?", (pago_id,))

                                    for i in range(int(num_partes)):
                                        vence_div = fecha_primera + relativedelta(months=i)
                                        nueva_nota = f"{nota_orig_txt} (PARTE {i+1}/{int(num_partes)})"
                                        cursor_div.execute(
                                            """
                                            INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas)
                                            VALUES (?, ?, ?, 'Pendiente', ?)
                                        """,
                                            (
                                                ord_id,
                                                monto_nueva_cuota,
                                                vence_div.strftime("%Y-%m-%d"),
                                                nueva_nota,
                                            ),
                                        )

                                    conn_div.commit()
                                st.success(
                                    f"✅ ¡Pago divido exitosamente en {num_partes} cuotas!"
                                )
                                time.sleep(1)
                                st.rerun()

                    with col_btn2:
                        r_wa = pagos_cliente[pagos_cliente["ID"] == pago_id].iloc[0]
                        monto_wa = r_wa['Monto']

                        msg = (
                            f"Estimado cliente de {r_wa['Negocio']},\n\n"
                            "Le enviamos un recordatorio de su cuota pendiente:\n"
                            f"📌 Detalle: {r_wa['Detalle']}\n"
                            f"💰 Monto: {monto_wa}\n"
                            f"📅 Vencimiento: {r_wa['Vence']}\n\n"
                            "¡Saludos!"
                        )

                        st.markdown("---")
                        st.caption("🔍 Previsualización del mensaje:")
                        st.info(msg)

                        tel = str(r_wa["Telefono"]).replace(" ", "").replace("+", "")
                        if tel:
                            link = f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"
                            st.markdown(
                                f"[📲 Enviar WhatsApp a {empresa}]({link})",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.warning("El cliente no cuenta con número de teléfono registrado.")

            total_general = df_p["Monto"].sum()
            st.divider()
            st.metric(
                "Total General a Cobrar", f"{int(total_general):,} Gs.".replace(",", ".")
            )

        else:
            st.info("No hay cobros pendientes por el momento.")

        st.markdown("---")
        with st.expander("⚠️ Zona de Limpieza (Solo errores de carga)"):
            id_borrar = st.number_input("ID del pago a eliminar", min_value=0, step=1, key="del_pago_id")
            if st.button("🗑️ Eliminar Permanentemente", key="btn_del_pago"):
                conn.execute("DELETE FROM pagos WHERE id = ?", (id_borrar,))
                conn.commit()
                st.rerun()

        with st.expander("✏️ Editar Nota Manualmente"):
            id_nota = st.number_input(
                "ID del pago a modificar", min_value=1, step=1, key="input_id_nota"
            )
            texto_nota = st.text_input("Texto de la nota", key="input_texto_nota")
            if st.button("Actualizar Nota en BD", key="btn_act_nota"):
                with get_connection() as conn_nota:
                    conn_nota.execute(
                        "UPDATE pagos SET notas = ? WHERE id = ?",
                        (texto_nota.upper(), id_nota),
                    )
                    conn_nota.commit()
                st.success(f"¡Nota actualizada para el ID {id_nota}!")
                st.rerun()
                
    except Exception as e:
        st.error(f"⚠️ Ocurrió un error al cargar 'Cobros Pendientes': {e}")
        import traceback
        st.code(traceback.format_exc())