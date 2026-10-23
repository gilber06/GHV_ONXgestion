import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime
import urllib.parse
import os

DB_PATH = os.getenv("DB_PATH", "database/gestion.db")

def render(get_connection):
    st.title("Gestión de Taller y Recepción de Equipos")
    
    conn = get_connection()

    tab_rec1, tab_rec2, tab_rec3 = st.tabs([
        "📥 Ingresar Nuevo Equipo",
        "📋 Equipos en Taller",
        "💬 Enviar Comprobante / Aviso",
    ])

    df_clientes_rec = pd.read_sql_query(
        "SELECT id, apodo || ' - ' || nombre as cliente_display FROM clientes WHERE activo = 1",
        conn,
    )

    with tab_rec1:
        st.subheader("Formulario de Entrada de Equipos (Recepción)")
        if df_clientes_rec.empty:
            st.warning("⚠️ Primero debes registrar un cliente en 'Gestión de Clientes'.")
        else:
            cli_dict_rec = dict(
                zip(
                    df_clientes_rec["cliente_display"], df_clientes_rec["id"]
                )
            )

            with st.form("form_nueva_recepcion_equipo", clear_on_submit=True):
                cli_sel_rec = st.selectbox(
                    "Cliente / Empresa:", options=list(cli_dict_rec.keys())
                )

                c_eq1, c_eq2 = st.columns(2)
                with c_eq1:
                    tipo_equipo = st.selectbox("Tipo de Equipo:", [
                        "IMPRESORA",
                        "NOTEBOOK",
                        "PC DE ESCRITORIO",
                        "CCTV / CÁMARA",
                        "UPS / FUENTE",
                        "MONITOR",
                        "OTRO",
                    ])
                    marca_modelo = (
                        st.text_input(
                            "Marca y Modelo",
                            placeholder="Ej: Brother DCP-T520W / HP Pavilion 15",
                        )
                        .strip()
                        .upper()
                    )
                with c_eq2:
                    numero_serie = (
                        st.text_input("Número de Serie (S/N) [Opcional]").strip().upper()
                    )
                    accesorios = (
                        st.text_input(
                            "Accesorios Dejados",
                            placeholder="Ej: Fuente de poder, Cable USB, Cartucho extra",
                        )
                        .strip()
                        .upper()
                    )

                falla_reportada = (
                    st.text_area(
                        "Falla Reportada por el Cliente / Motivo de Ingreso:"
                    )
                    .strip()
                    .upper()
                )

                btn_ingresar_eq = st.form_submit_button(
                    "📥 Registrar Recepción de Equipo"
                )

            if btn_ingresar_eq:
                if not marca_modelo or not falla_reportada:
                    st.error("⚠️ Por favor completa la Marca/Modelo y la Falla Reportada.")
                else:
                    try:
                        with sqlite3.connect(DB_PATH) as conn_ot:
                            cursor_ot = conn_ot.cursor()
                            cursor_ot.execute(
                                """
                                INSERT INTO ordenes_trabajo 
                                (id_cliente, tipo_equipo, marca_modelo, numero_serie, accesorios, falla_reportada, estado, sincronizado)
                                VALUES (?, ?, ?, ?, ?, ?, 'Pendiente de Revisión', 0)
                            """,
                                (
                                    cli_dict_rec[cli_sel_rec],
                                    tipo_equipo,
                                    marca_modelo,
                                    numero_serie,
                                    accesorios,
                                    falla_reportada,
                                ),
                            )
                            conn_ot.commit()
                            nueva_ot_id = cursor_ot.lastrowid
                        st.success(
                            "✅ ¡Equipo registrado exitosamente con la Orden de Trabajo N°"
                            f" #{nueva_ot_id}!"
                        )
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al recepcionar el equipo: {e}")

    with tab_rec2:
        st.subheader("Control de Trabajo y Diagnósticos")

        df_taller = pd.read_sql_query(
            """
                SELECT 
                    ot.id_orden as [OT #],
                    COALESCE(NULLIF(c.apodo, ''), c.nombre) as Cliente,
                    c.telefono as Telefono,
                    ot.tipo_equipo as Tipo,
                    ot.marca_modelo as [Marca / Modelo],
                    ot.numero_serie as [N° Serie],
                    ot.accesorios as Accesorios,
                    ot.falla_reportada as Falla,
                    COALESCE(ot.diagnostico_tecnico, '') as Diagnostico,
                    ot.monto_presupuesto as Presupuesto,
                    ot.estado as Estado,
                    ot.fecha_ingreso as [Fecha Ingreso],
                    ot.id_cliente
                FROM ordenes_trabajo ot
                JOIN clientes c ON ot.id_cliente = c.id
                ORDER BY ot.id_orden DESC
            """,
            conn,
        )

        if not df_taller.empty:
            estados_lista = [
                "TODOS",
                "Pendiente de Revisión",
                "Presupuestado",
                "Aprobado",
                "En Producción",
                "Listo para Entrega",
                "Entregado",
                "Rechazado",
            ]
            filtro_est = st.selectbox("Filtrar por Estado de Taller:", estados_lista)

            df_taller_vista = df_taller.copy()
            if filtro_est != "TODOS":
                df_taller_vista = df_taller_vista[
                    df_taller_vista["Estado"] == filtro_est
                ]

            df_taller_display = df_taller_vista.drop(columns=["Telefono", "id_cliente"])
            df_taller_display["Presupuesto"] = df_taller_display["Presupuesto"].apply(
                lambda x: (
                    f"{int(x):,} Gs.".replace(",", ".")
                    if pd.notna(x)
                    else "0 Gs."
                )
            )
            st.dataframe(
                df_taller_display, use_container_width=True, hide_index=True
            )

            st.markdown("---")
            st.subheader("🔧 Actualizar Diagnóstico y Estado de Equipo")

            ot_taller_dict = {
                f"OT #{row['OT #']} - {row['Cliente']} ({row['Marca / Modelo']})": row
                for _, row in df_taller.iterrows()
            }
            ot_taller_sel = st.selectbox(
                "Seleccione Orden para gestionar:", list(ot_taller_dict.keys())
            )

            datos_ot_taller = ot_taller_dict[ot_taller_sel]
            id_ot_actual = int(datos_ot_taller["OT #"])

            val_presup_def = (
                int(datos_ot_taller["Presupuesto"])
                if pd.notna(datos_ot_taller["Presupuesto"])
                else 0
            )
            val_diag_def = (
                str(datos_ot_taller["Diagnostico"])
                if pd.notna(datos_ot_taller["Diagnostico"])
                and str(datos_ot_taller["Diagnostico"]).lower() != "nan"
                else ""
            )

            with st.form("form_gestion_taller"):
                col_g1, col_g2 = st.columns(2)

                lista_estados = [
                    "Pendiente de Revisión",
                    "Presupuestado",
                    "Aprobado",
                    "Rechazado",
                    "En Producción",
                    "Listo para Entrega",
                    "Entregado",
                ]
                idx_est_act = (
                    lista_estados.index(datos_ot_taller["Estado"])
                    if datos_ot_taller["Estado"] in lista_estados
                    else 0
                )

                with col_g1:
                    nuevo_est_ot = st.selectbox(
                        "Estado del Trabajo:", options=lista_estados, index=idx_est_act
                    )
                    monto_presup = st.number_input(
                        "Monto del Presupuesto (Gs):",
                        min_value=0,
                        value=val_presup_def,
                        step=25000,
                    )

                with col_g2:
                    diag_tec = (
                        st.text_area(
                            "Diagnóstico Técnico / Solución Realizada:",
                            value=val_diag_def,
                        )
                        .strip()
                        .upper()
                    )

                sincronizar_cobro = st.checkbox(
                    "⚡ Si pasa a 'Aprobado' o 'En Producción', generar cobro pendiente en Cartera de Clientes",
                    value=True,
                )

                btn_up_ot = st.form_submit_button("💾 Guardar Cambios en Taller")

            if btn_up_ot:
                try:
                    with sqlite3.connect(DB_PATH) as conn_up_ot:
                        cursor_up = conn_up_ot.cursor()
                        cursor_up.execute(
                            """
                            UPDATE ordenes_trabajo 
                            SET estado = ?, diagnostico_tecnico = ?, monto_presupuesto = ?, fecha_modificacion = CURRENT_TIMESTAMP, sincronizado = 0
                            WHERE id_orden = ?
                        """,
                            (nuevo_est_ot, diag_tec, monto_presup, id_ot_actual),
                        )

                        if (
                            sincronizar_cobro
                            and nuevo_est_ot in ["Aprobado", "En Producción"]
                            and monto_presup > 0
                        ):
                            desc_orden = (
                                f"REPARACIÓN/TALLER: {datos_ot_taller['Marca / Modelo']} (OT #{id_ot_actual})"
                            )
                            cursor_up.execute(
                                """
                                INSERT INTO ordenes (negocio_id, cliente_id, descripcion, fecha_ingreso, monto_total, costo_insumos, estado, sincronizado)
                                VALUES (1, ?, ?, ?, ?, 0, 'En Proceso', 0)
                            """,
                                (
                                    datos_ot_taller["id_cliente"],
                                    desc_orden,
                                    datetime.now().strftime("%Y-%m-%d"),
                                    monto_presup,
                                ),
                            )

                            nueva_ord_id = cursor_up.lastrowid

                            cursor_up.execute(
                                """
                                INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas, sincronizado)
                                VALUES (?, ?, ?, 'Pendiente', ?, 0)
                            """,
                                (
                                    nueva_ord_id,
                                    monto_presup,
                                    datetime.now().strftime("%Y-%m-%d"),
                                    f"TALLER OT #{id_ot_actual}",
                                ),
                            )

                        conn_up_ot.commit()
                    st.success("✅ ¡Orden de Trabajo de Taller actualizada!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al actualizar: {e}")
        else:
            st.info("No hay equipos ingresados en el taller.")

    with tab_rec3:
        st.subheader("Generación de Avisos WhatsApp")
        if not df_taller.empty:
            ot_msj_dict = {
                f"OT #{row['OT #']} - {row['Cliente']} ({row['Marca / Modelo']})": row
                for _, row in df_taller.iterrows()
            }
            ot_msj_sel = st.selectbox(
                "Seleccionar OT para notificar:",
                list(ot_msj_dict.keys()),
                key="sel_msj_wa",
            )

            row_wa = ot_msj_dict[ot_msj_sel]
            monto_p_raw = (
                int(row_wa["Presupuesto"]) if pd.notna(row_wa["Presupuesto"]) else 0
            )
            monto_pres_fmt = f"{monto_p_raw:,}".replace(",", ".")

            tipo_mensaje = st.radio(
                "Tipo de Notificación:",
                [
                    "📥 Recepción de Equipo",
                    "💡 Presupuesto / Diagnóstico",
                    "✅ Trabajo Terminado / Listo para Entrega",
                ],
            )

            diag_wa_txt = (
                str(row_wa["Diagnostico"])
                if pd.notna(row_wa["Diagnostico"])
                and str(row_wa["Diagnostico"]).lower() != "nan"
                and str(row_wa["Diagnostico"]).strip() != ""
                else "Revisión concluida"
            )

            if tipo_mensaje == "📥 Recepción de Equipo":
                msg_taller = (
                    f"Hola *{row_wa['Cliente']}*, le saludamos de *GHV-Service*.\n\n"
                    f"Confirmamos la recepción de su equipo:\n📌 *OT N°:*"
                    f" #{row_wa['OT #']}\n💻 *Equipo:* {row_wa['Tipo']}"
                    f" {row_wa['Marca / Modelo']}\n🔎 *Falla Reportada:*"
                    f" {row_wa['Falla']}\n🔌 *Accesorios:*"
                    f" {row_wa['Accesorios'] if row_wa['Accesorios'] else 'Ninguno'}\n\nLe"
                    " avisaremos tan pronto tengamos el diagnóstico técnico completado."
                    " ¡Gracias!"
                )
            elif tipo_mensaje == "💡 Presupuesto / Diagnóstico":
                msg_taller = (
                    f"Hola *{row_wa['Cliente']}*, le saludamos de *GHV-Service*.\n\nLe"
                    " informamos el diagnóstico para su equipo (OT"
                    f" #{row_wa['OT #']}):\n💻 *Equipo:* {row_wa['Marca / Modelo']}\n🔬"
                    f" *Diagnóstico:* {diag_wa_txt}\n💰 *Presupuesto:*"
                    f" {monto_pres_fmt} Gs.\n\nAguardamos su confirmación para proceder"
                    " con la reparación."
                )
            else:
                msg_taller = (
                    f"Hola *{row_wa['Cliente']}*, le saludamos de *GHV-Service*.\n\n¡Su"
                    " equipo ya está *LISTO PARA ENTREGA*! 🎉\n📌 *OT N°:*"
                    f" #{row_wa['OT #']}\n💻 *Equipo:* {row_wa['Marca / Modelo']}\n🛠️"
                    f" *Trabajo Realizado:* {diag_wa_txt}\n💰 *Monto a Cancelar:*"
                    f" {monto_pres_fmt} Gs.\n\nPuede pasar a retirarlo en nuestro"
                    " horario de atención."
                )

            st.markdown("---")
            st.caption("🔍 Previsualización del mensaje:")
            st.info(msg_taller)

            tel_clean = (
                str(row_wa["Telefono"])
                .replace(" ", "")
                .replace("+", "")
                .replace("None", "")
            )
            link_wa = (
                f"https://wa.me/{tel_clean}?text={urllib.parse.quote(msg_taller)}"
            )
            st.markdown(
                f"[📲 Enviar Notificación por WhatsApp a {row_wa['Cliente']}]({link_wa})",
                unsafe_allow_html=True,
            )
        else:
            st.info("No hay registradas OTs para generar avisos.")