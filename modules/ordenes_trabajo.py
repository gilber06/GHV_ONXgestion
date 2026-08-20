from datetime import datetime
import os
from pathlib import Path
import sqlite3
import urllib.parse

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st
from modules.database import get_connection  # Importa la conexión híbrida centralizada
from sincronizador import ejecutar_sincronizacion_completa

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


def render():
    st.header("📝 Recepción de Equipos y Órdenes de Trabajo")
    st.caption("Registrá el ingreso de equipos al taller, generá comprobantes de recepción y hacé seguimiento directo en la base de datos.")
    st.markdown("---")

    # Asegurar conexión y obtener clientes existentes para el selector
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Obtener lista de clientes para asociar la OT
            clientes_db = cursor.execute("SELECT id, nombre, telefono FROM clientes ORDER BY nombre").fetchall()
    except Exception as e:
        st.error(f"❌ Error al conectar con la base de datos: {e}")
        return

    col_form, col_lista = st.columns([1, 1], gap="medium")

    with col_form:
        st.subheader("📌 Nueva Orden de Trabajo")
        
        with st.form("form_nueva_ot", clear_on_submit=True):
            # Selección de cliente existente o ingreso rápido
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

            submitted = st.form_submit_button("📥 Registrar Orden en Base de Datos", use_container_width=True)

            if submitted:
                if not ot_cliente or not ot_falla or not ot_marca:
                    st.error("Por favor completá los campos obligatorios: Cliente, Marca/Modelo y Falla.")
                else:
                    try:
                        with get_connection() as conn_ins:
                            cur = conn_ins.cursor()
                            
                            # 1. Asegurar que el cliente exista en la tabla clientes y obtener ID
                            cur.execute("SELECT id FROM clientes WHERE nombre = ?", (ot_cliente,))
                            res_cli = cur.fetchone()
                            if res_cli:
                                cliente_id = res_cli[0]
                            else:
                                cur.execute("INSERT INTO clientes (nombre, telefono, sincronizado) VALUES (?, ?, 0)", (ot_cliente, ot_telefono))
                                if hasattr(cur, "lastrowid") and cur.lastrowid:
                                    cliente_id = cur.lastrowid
                                else:
                                    cur.execute("SELECT MAX(id) FROM clientes")
                                    cliente_id = cur.fetchone()[0]

                            # 2. Insertar en ordenes_trabajo
                            cur.execute("""
                                INSERT INTO ordenes_trabajo 
                                (id_cliente, tipo_equipo, marca_modelo, numero_serie, accesorios, falla_reportada, monto_presupuesto, estado, sincronizado)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente de Revisión', 0)
                            """, (cliente_id, ot_tipo, ot_marca, ot_serie, ot_accesorios, ot_falla, ot_presupuesto))
                            
                            if hasattr(cur, "lastrowid") and cur.lastrowid:
                                nuevo_id_ot = cur.lastrowid
                            else:
                                cur.execute("SELECT MAX(id_orden) FROM ordenes_trabajo")
                                nuevo_id_ot = cur.fetchone()[0]
                                
                            conn_ins.commit()
                            ejecutar_sincronizacion_completa()

                        num_ot_str = f"OT-{nuevo_id_ot:03d}"
                        
                        # Preparar diccionario para el PDF
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

                        st.success(f"¡Orden #{num_ot_str} registrada con éxito en la base de datos!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error al guardar en la base de datos: {e}")

        # Sección de descarga del último comprobante generado
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

    with col_lista:
        st.subheader("📋 Equipos en Taller (Base de Datos)")

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
            st.info("Aún no hay órdenes de trabajo registradas en la base de datos.")
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
                                    "UPDATE ordenes_trabajo SET estado = ?, fecha_modificacion = CURRENT_TIMESTAMP, sincronizado = 0 WHERE id_orden = ?",
                                    (nuevo_estado, ot['id_orden'])
                                )
                                conn_upd.commit()
                                ejecutar_sincronizacion_completa()
                            st.toast(f"Orden {ot_num} actualizada a '{nuevo_estado}'", icon="🔄")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar estado: {e}")

                    # Botón de notificación por WhatsApp
                    tel_cliente = ot["cliente_tel"]
                    if tel_cliente:
                        clean_p = "".join(filter(str.isdigit, str(tel_cliente)))
                        nombre_empresa = st.session_state.get("config_negocio", {}).get("nombre", "GHV Service")
                        
                        if nuevo_estado == "Listo para Retiro":
                            txt_wa = f"Hola {ot['cliente_nombre']}, ¡excelentes noticias! Tu equipo ({ot['tipo_equipo']}) bajo la orden {ot_num} ya está LISTO PARA RETIRAR en {nombre_empresa}."
                        else:
                            txt_wa = f"Hola {ot['cliente_nombre']}, te actualizamos sobre la orden {ot_num}: El estado actual de tu equipo es '{nuevo_estado}'."
                        
                        wa_url = f"https://wa.me/{clean_p}?text={urllib.parse.quote(txt_wa)}"
                        st.link_button(f"📲 Avisar por WhatsApp ({nuevo_estado})", wa_url, use_container_width=True)