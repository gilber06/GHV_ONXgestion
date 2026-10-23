import os
import streamlit as st
import pandas as pd
import sqlite3
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from dateutil.relativedelta import relativedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image

# Determinación inteligente de rutas para assets/ y output/
RUTA_ACTUAL = Path(__file__).resolve()
BASE_DIR = (
    RUTA_ACTUAL.parent.parent
    if RUTA_ACTUAL.parent.name == "modules"
    else RUTA_ACTUAL.parent
)
OUTPUT_DIR = BASE_DIR / "output"

def generar_pdf_ot(ot, filename="orden_trabajo.pdf"):
    """Genera el comprobante físico de recepción de taller en PDF."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ruta_salida = OUTPUT_DIR / filename

    cfg = st.session_state.get("config_negocio", {
        "nombre": "GHV - Service",
        "rubro": "Soporte Técnico",
        "ruc": "",
        "telefono": "",
        "correo": "",
        "direccion": "",
        "logo_path": ""
    })

    doc = SimpleDocTemplate(str(ruta_salida), pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    empresa_style = ParagraphStyle('EmpresaStyle', parent=styles['Heading2'], fontSize=15, textColor=colors.HexColor("#0F172A"), leading=17)
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor("#475569"), leading=11)
    contacto_style = ParagraphStyle('ContactoStyle', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor("#64748B"), leading=10)

    info_contacto_str = f"<b>RUC:</b> {cfg.get('ruc', '')} | <b>Tel:</b> {cfg.get('telefono', '')} | <b>Email:</b> {cfg.get('correo', '')} | {cfg.get('direccion', '')}"

    texto_header = [
        Paragraph(f"<b>{cfg['nombre']}</b>", empresa_style),
        Spacer(1, 2),
        Paragraph(cfg['rubro'], sub_style),
        Spacer(1, 3),
        Paragraph(info_contacto_str, contacto_style)
    ]

    logo_path = cfg.get("logo_path")
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=60, height=40)
            img.hAlign = 'LEFT'
            header_table = Table([[img, texto_header]], colWidths=[70, 470])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
            ]))
            story.append(header_table)
        except Exception:
            for el in texto_header:
                story.append(el)
    else:
        for el in texto_header:
            story.append(el)

    story.append(Spacer(1, 15))

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor("#1E293B"))
    story.append(Paragraph(f"COMPROBANTE DE RECEPCIÓN - OT N° {ot['numero']}", title_style))
    story.append(Spacer(1, 10))

    data = [
        [Paragraph("<b>Fecha de Ingreso:</b>", styles['Normal']), str(ot['fecha'])],
        [Paragraph("<b>Cliente:</b>", styles['Normal']), str(ot['cliente'])],
        [Paragraph("<b>Teléfono / WA:</b>", styles['Normal']), str(ot['telefono'])],
        [Paragraph("<b>Equipo / Dispositivo:</b>", styles['Normal']), str(ot['equipo'])],
        [Paragraph("<b>Número de Serie / ID:</b>", styles['Normal']), str(ot['serie']) if ot['serie'] else "S/N"],
        [Paragraph("<b>Accesorios Incluidos:</b>", styles['Normal']), str(ot['accesorios']) if ot['accesorios'] else "Ninguno"],
        [Paragraph("<b>Falla Reportada:</b>", styles['Normal']), str(ot['falla'])],
    ]

    t = Table(data, colWidths=[150, 390])
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F8FAFC")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)

    story.append(Spacer(1, 25))
    note_style = ParagraphStyle('NoteStyle', parent=styles['Italic'], fontSize=8, textColor=colors.HexColor("#64748B"))
    story.append(Paragraph("* Presente este comprobante para el retiro de su equipo.", note_style))
    story.append(Paragraph("* La empresa no se responsabiliza por pérdida de datos. Se recomienda respaldo previo.", note_style))

    doc.build(story)
    return ruta_salida

def render(get_connection):
    st.title("📝 Órdenes de Trabajo y Taller")
    
    tab_rec, tab_taller, tab_gestion, tab_papelera = st.tabs([
        "📥 Nueva Recepción (PDF)", 
        "📋 Equipos en Taller", 
        "🛠️ Gestión Financiera y Reajuste", 
        "♻️ Papelera"
    ])

    # ==========================================
    # PESTAÑA 1: NUEVA RECEPCIÓN Y PDF
    # ==========================================
    with tab_rec:
        st.subheader("Registrar Ingreso de Equipo al Taller")
        
        try:
            with get_connection() as conn_c:
                conn_c.row_factory = sqlite3.Row
                clientes_db = conn_c.execute("""
                    SELECT MIN(id) as id, nombre, MAX(telefono) as telefono 
                    FROM clientes 
                    WHERE nombre IS NOT NULL AND nombre != '' 
                    GROUP BY nombre 
                    ORDER BY nombre ASC
                """).fetchall()
        except Exception as e:
            st.error(f"❌ Error al cargar clientes: {e}")
            clientes_db = []

        with st.form("form_nueva_ot_taller", clear_on_submit=True):
            nombres_clientes = [c["nombre"] for c in clientes_db] if clientes_db else []
            nombres_clientes.insert(0, "-- Otro / Cliente Nuevo --")
            
            cliente_seleccionado = st.selectbox("Seleccionar Cliente Registrado", nombres_clientes)
            
            if cliente_seleccionado == "-- Otro / Cliente Nuevo --":
                ot_cliente = st.text_input("Nombre del Nuevo Cliente")
                ot_telefono = st.text_input("WhatsApp del Cliente (ej: 595981xxxxxx)")
            else:
                cliente_obj = next((c for c in clientes_db if c["nombre"] == cliente_seleccionado), None)
                ot_cliente = cliente_seleccionado
                ot_telefono = cliente_obj["telefono"] if cliente_obj and cliente_obj["telefono"] else ""
                st.info(f"Teléfono vinculado: {ot_telefono if ot_telefono else 'No registrado'}")

            c_tipo, c_marca = st.columns(2)
            with c_tipo:
                ot_tipo = st.selectbox("Tipo de Equipo", ["Notebook / Laptop", "PC de Escritorio", "Impresora", "Cámara / CCTV", "Servidor", "UPS", "Otro"])
            with c_marca:
                ot_marca = st.text_input("Marca y Modelo (ej: HP ProBook 440 G6)")

            c_mod, c_serie = st.columns(2)
            with c_mod:
                ot_presupuesto = st.number_input("Presupuesto Estimado (Gs.)", min_value=0, value=0, step=50000)
            with c_serie:
                ot_serie = st.text_input("N° de Serie / ID (Opcional)")

            ot_accesorios = st.text_input("Accesorios Incluidos (ej: Cargador, Mochila)")
            ot_falla = st.text_area("Falla Reportada / Diagnóstico Inicial")

            submitted = st.form_submit_button("📥 Registrar Orden y Generar PDF", use_container_width=True)

            if submitted:
                if not ot_cliente or not ot_falla or not ot_marca:
                    st.error("Por favor completá los campos obligatorios: Cliente, Marca/Modelo y Falla.")
                else:
                    try:
                        with get_connection() as conn_ins:
                            cur = conn_ins.cursor()
                            cur.execute("SELECT id FROM clientes WHERE nombre = ?", (ot_cliente,))
                            res_cli = cur.fetchone()
                            if res_cli:
                                cliente_id = res_cli[0]
                            else:
                                cur.execute("INSERT INTO clientes (nombre, telefono, activo) VALUES (?, ?, 1)", (ot_cliente, ot_telefono))
                                if hasattr(cur, "lastrowid") and cur.lastrowid:
                                    cliente_id = cur.lastrowid
                                else:
                                    cur.execute("SELECT MAX(id) FROM clientes")
                                    cliente_id = cur.fetchone()[0]

                            # 1. Insertar en la tabla de taller (ordenes_trabajo)[cite: 13]
                            cur.execute("""
                                INSERT INTO ordenes_trabajo 
                                (id_cliente, tipo_equipo, marca_modelo, numero_serie, accesorios, falla_reportada, monto_presupuesto, estado)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente de Revisión')
                            """, (cliente_id, ot_tipo, ot_marca, ot_serie, ot_accesorios, ot_falla, ot_presupuesto))
                            
                            if hasattr(cur, "lastrowid") and cur.lastrowid:
                                nuevo_id_ot = cur.lastrowid
                            else:
                                cur.execute("SELECT MAX(id_orden) FROM ordenes_trabajo")
                                nuevo_id_ot = cur.fetchone()[0]

                            # 2. AUTOMATIZACIÓN FINANCIERA: Insertar en la tabla comercial 'ordenes'[cite: 13]
                            detalle_financiero = f"{ot_tipo} - {ot_marca} (Falla: {ot_falla})"
                            
                            try:
                                cur.execute("SELECT id FROM negocios LIMIT 1")
                                neg_res = cur.fetchone()
                                negocio_id = neg_res[0] if neg_res else 1
                            except Exception:
                                negocio_id = 1

                            cur.execute("""
                                INSERT INTO ordenes (cliente_id, descripcion, monto_total, costo_insumos, estado, negocio_id)
                                VALUES (?, ?, ?, 0, 'Pendiente', ?)
                            """, (cliente_id, detalle_financiero.upper(), ot_presupuesto, negocio_id))
                            
                            if hasattr(cur, "lastrowid") and cur.lastrowid:
                                id_orden_financiera = cur.lastrowid
                            else:
                                cur.execute("SELECT MAX(id) FROM ordenes")
                                id_orden_financiera = cur.fetchone()[0]

                            # 3. Crear automáticamente el pago pendiente inicial en la tabla 'pagos'[cite: 13]
                            if ot_presupuesto > 0:
                                cur.execute("""
                                    INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas)
                                    VALUES (?, ?, ?, 'Pendiente', 'SALDO PENDIENTE OT')
                                """, (id_orden_financiera, ot_presupuesto, datetime.now().strftime("%Y-%m-%d")))
                                
                            conn_ins.commit()

                        num_ot_str = f"OT-{nuevo_id_ot:03d}"
                        datos_ot_pdf = {
                            "numero": num_ot_str,
                            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "cliente": ot_cliente,
                            "telefono": ot_telefono,
                            "equipo": f"{ot_tipo} - {ot_marca}",
                            "serie": ot_serie,
                            "accesorios": ot_accesorios,
                            "falla": ot_falla
                        }

                        ruta_pdf = generar_pdf_ot(datos_ot_pdf, f"Comprobante_{num_ot_str}.pdf")
                        
                        st.session_state.ot_pdf_ready = True
                        st.session_state.ot_pdf_path = str(ruta_pdf)
                        st.session_state.ot_actual_num = num_ot_str

                        st.success(f"¡Orden #{num_ot_str} registrada y vinculada a finanzas con éxito!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error al guardar: {e}")

        if st.session_state.get("ot_pdf_ready") and os.path.exists(st.session_state.get("ot_pdf_path", "")):
            st.markdown("---")
            st.markdown(f"#### Comprobante listo: **{st.session_state.ot_actual_num}**")
            with open(st.session_state.ot_pdf_path, "rb") as pdf_file:
                st.download_button(
                    label="📥 Descargar Comprobante PDF",
                    data=pdf_file,
                    file_name=f"Comprobante_{st.session_state.ot_actual_num}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

    # ==========================================
    # PESTAÑA 2: EQUIPOS EN TALLER
    # ==========================================
    with tab_taller:
        st.subheader("Seguimiento de Equipos en Taller")
        try:
            with get_connection() as conn_read:
                conn_read.row_factory = sqlite3.Row
                cursor_read = conn_read.cursor()
                query_ots = """
                    SELECT ot.*, c.nombre AS cliente_nombre, c.telefono AS cliente_tel
                    FROM ordenes_trabajo ot
                    JOIN clientes c ON ot.id_cliente = c.id
                    ORDER BY ot.id_orden DESC
                """
                ots_registradas = cursor_read.execute(query_ots).fetchall()
        except Exception as e:
            st.error(f"No se pudieron cargar las órdenes: {e}")
            ots_registradas = []

        if not ots_registradas:
            st.info("Aún no hay órdenes de trabajo en taller.")
        else:
            for ot in ots_registradas:
                ot_num = f"OT-{ot['id_orden']:03d}"
                with st.expander(f"📌 **{ot_num}** | {ot['cliente_nombre']} - {ot['tipo_equipo']} ({ot['marca_modelo']})"):
                    st.write(f"**Fecha Ingreso:** {ot['fecha_ingreso']}")
                    st.write(f"**Falla Reportada:** {ot['falla_reportada']}")
                    st.write(f"**Accesorios:** {ot['accesorios'] if ot['accesorios'] else 'Ninguno'}")
                    st.write(f"**Presupuesto:** Gs. {ot['monto_presupuesto']:,.0f}".replace(",", "."))

                    estados_posibles = [
                        'Pendiente de Revisión', 
                        'En Diagnóstico', 
                        'Esperando Repuesto', 
                        'Listo para Retiro', 
                        'Entregado'
                    ]
                    estado_actual = ot["estado"] if ot["estado"] in estados_posibles else 'Pendiente de Revisión'
                    
                    nuevo_estado = st.selectbox(
                        "Estado de la Orden:",
                        estados_posibles,
                        index=estados_posibles.index(estado_actual),
                        key=f"est_db_{ot['id_orden']}"
                    )

                    if nuevo_estado != ot["estado"]:
                        try:
                            with get_connection() as conn_upd:
                                conn_upd.execute(
                                    "UPDATE ordenes_trabajo SET estado = ?, fecha_modificacion = CURRENT_TIMESTAMP WHERE id_orden = ?",
                                    (nuevo_estado, ot['id_orden'])
                                )
                                conn_upd.commit()
                            st.toast(f"Orden {ot_num} actualizada a '{nuevo_estado}'", icon="🔄")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar estado: {e}")

                    tel_cliente = ot["cliente_tel"]
                    if tel_cliente:
                        clean_p = "".join(filter(str.isdigit, str(tel_cliente)))
                        nombre_empresa = st.session_state.get("config_negocio", {}).get("nombre", "GHV Service")
                        if nuevo_estado == "Listo para Retiro":
                            txt_wa = f"Hola {ot['cliente_nombre']}, ¡excelentes noticias! Tu equipo ({ot['tipo_equipo']}) bajo la orden {ot_num} ya está LISTO PARA RETIRAR en {nombre_empresa}."
                        else:
                            txt_wa = f"Hola {ot['cliente_nombre']}, te actualizamos sobre la orden {ot_num}: El estado actual de tu equipo es '{nuevo_estado}'."
                        
                        wa_url = f"https://wa.me/{clean_p}?text={urllib.parse.quote(txt_wa)}"
                        st.link_button(f"📲 Avisar por WhatsApp ({nuevo_estado})", wa_url)

    # ==========================================
    # PESTAÑA 3: GESTIÓN FINANCIERA Y REAJUSTE
    # ==========================================
    with tab_gestion:
        st.subheader("Gestión Comercial y Reajuste de Saldos (Tabla Órdenes)")
        
        with get_connection() as conn_g:
            df_ot_edit = pd.read_sql_query(
                """
                SELECT o.id, 
                       COALESCE(NULLIF(c.apodo, ''), c.nombre) as Empresa, 
                       o.descripcion, 
                       o.monto_total, 
                       o.costo_insumos, 
                       o.estado 
                FROM ordenes o 
                JOIN clientes c ON o.cliente_id = c.id
                ORDER BY o.id DESC
            """,
                conn_g,
            )

        if not df_ot_edit.empty:
            ot_opciones = {
                f"OT {row['id']} - {row['Empresa']}": row
                for _, row in df_ot_edit.iterrows()
            }
            ot_seleccionada = st.selectbox(
                "Seleccione la OT para modificar:", options=list(ot_opciones.keys())
            )

            datos_ot = ot_opciones[ot_seleccionada]
            ot_id = int(datos_ot["id"])

            with get_connection() as conn_pagos:
                df_pagos_ot = pd.read_sql_query(
                    f"SELECT id, monto_cuota, estado, notas FROM pagos WHERE orden_id = {ot_id}",
                    conn_pagos,
                )

            entrega_actual_val = 0
            if not df_pagos_ot.empty:
                entrega_actual_val = df_pagos_ot[
                    df_pagos_ot["notas"].fillna("") == "ENTREGA INICIAL"
                ]["monto_cuota"].sum()

            monto_tot_def = int(datos_ot["monto_total"]) if pd.notna(datos_ot["monto_total"]) else 0
            costo_ins_def = int(datos_ot["costo_insumos"]) if pd.notna(datos_ot["costo_insumos"]) else 0
            desc_ot_def = str(datos_ot["descripcion"]) if pd.notna(datos_ot["descripcion"]) else ""

            with st.form("form_edicion_completa_ot"):
                col_ot1, col_ot2 = st.columns(2)
                estados_permitidos = ["Pendiente", "En Proceso", "Finalizada", "Cancelada", "Entregado", "Venta"]
                estado_actual = datos_ot["estado"]
                indice_default = estados_permitidos.index(estado_actual) if estado_actual in estados_permitidos else 0

                with col_ot1:
                    nuevo_monto = st.number_input("Monto Total:", value=monto_tot_def, step=50000)
                    st.info(f"Confirmar total: **{int(nuevo_monto):,} Gs.**".replace(",", "."))

                    nueva_entrega_ot = st.number_input("Entrega Inicial:", value=int(entrega_actual_val), step=50000)
                    st.info(f"Confirmar entrega: **{int(nueva_entrega_ot):,} Gs.**".replace(",", "."))

                    nuevo_estado = st.selectbox("Estado del Trabajo:", options=estados_permitidos, index=indice_default)

                with col_ot2:
                    nuevo_costo = st.number_input("Costo de Insumos / Repuestos:", value=costo_ins_def, step=10000)
                    st.info(f"Costo: **{int(nuevo_costo):,} Gs.**".replace(",", "."))
                    nueva_desc = st.text_area("Descripción detallada:", value=desc_ot_def)

                    cuotas_pendientes_count = len(df_pagos_ot[df_pagos_ot["estado"] == "Pendiente"]) if not df_pagos_ot.empty else 1
                    cant_cuotas_reajuste = st.number_input("Cantidad de Cuotas Restantes", min_value=1, value=max(cuotas_pendientes_count, 1))

                boton_guardar = st.form_submit_button("💾 Guardar Cambios y Reajustar Saldos")

            if boton_guardar:
                try:
                    with get_connection() as conn_edit:
                        cursor_edit = conn_edit.cursor()
                        cursor_edit.execute(
                            """
                            UPDATE ordenes 
                            SET monto_total = ?, costo_insumos = ?, descripcion = ?, estado = ? 
                            WHERE id = ?
                        """,
                            (int(nuevo_monto), int(nuevo_costo), nueva_desc.upper(), nuevo_estado, ot_id),
                        )

                        cursor_edit.execute("DELETE FROM pagos WHERE orden_id = ?", (ot_id,))

                        if nueva_entrega_ot > 0:
                            cursor_edit.execute(
                                """
                                INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas)
                                VALUES (?, ?, ?, 'Pagado', 'ENTREGA INICIAL')
                            """,
                                (ot_id, nueva_entrega_ot, datetime.now().strftime("%Y-%m-%d")),
                            )

                        saldo_restante_ot = nuevo_monto - nueva_entrega_ot
                        if saldo_restante_ot > 0:
                            if int(cant_cuotas_reajuste) == 1:
                                cursor_edit.execute(
                                    """
                                    INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas)
                                    VALUES (?, ?, ?, 'Pendiente', 'SALDO CONTADO')
                                """,
                                    (ot_id, saldo_restante_ot, datetime.now().strftime("%Y-%m-%d")),
                                )
                            else:
                                monto_por_cuota_ot = saldo_restante_ot / cant_cuotas_reajuste
                                for i in range(1, int(cant_cuotas_reajuste) + 1):
                                    vence_reajuste = datetime.now() + relativedelta(months=i)
                                    cursor_edit.execute(
                                        """
                                        INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas)
                                        VALUES (?, ?, ?, 'Pendiente', ?)
                                    """,
                                        (ot_id, monto_por_cuota_ot, vence_reajuste.strftime("%Y-%m-%d"), f"CUOTA {i}/{cant_cuotas_reajuste}"),
                                    )
                        conn_edit.commit()

                    st.success(f"✅ ¡OT {ot_id} reajustada y actualizada correctamente!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar: {e}")
        else:
            st.info("No hay órdenes financieras registradas.")

    # ==========================================
    # PESTAÑA 4: PAPELERA
    # ==========================================
    with tab_papelera:
        st.subheader("♻️ Papelera de Reciclaje e Historial")
        with get_connection() as conn_p:
            df_borrados = pd.read_sql_query("SELECT * FROM historial_eliminacion ORDER BY fecha_eliminacion DESC", conn_p)

        if not df_borrados.empty:
            st.dataframe(df_borrados, use_container_width=True)
            ultima = df_borrados.iloc[0]

            if st.button(f"↩️ Deshacer: Recuperar OT {int(ultima['orden_id'])}"):
                try:
                    with get_connection() as conn_undo:
                        conn_undo.execute(
                            """
                            INSERT INTO ordenes (id, monto_total, descripcion, estado, cliente_id, negocio_id)
                            VALUES (?, ?, ?, 'Pendiente', 
                                (SELECT id FROM clientes WHERE apodo = ? OR nombre = ? LIMIT 1), 
                                (SELECT id FROM negocios LIMIT 1))
                        """,
                            (int(ultima["orden_id"]), ultima["monto"], ultima["detalle"], ultima["cliente"], ultima["cliente"]),
                        )
                        conn_undo.execute("DELETE FROM historial_eliminacion WHERE id = ?", (int(ultima["id"]),))
                        conn_undo.commit()
                    st.success("Orden recuperada correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al recuperar: {e}")
        else:
            st.info("La papelera está vacía.")