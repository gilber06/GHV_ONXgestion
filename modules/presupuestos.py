from datetime import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import urllib.parse

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st
import pandas as pd
from modules.database import get_connection  # Importa la conexión híbrida centralizada[cite: 10]
from sincronizador import ejecutar_sincronizacion_completa

# Determinación inteligente de rutas[cite: 10]
RUTA_ACTUAL = Path(__file__).resolve()
BASE_DIR = (
    RUTA_ACTUAL.parent.parent
    if RUTA_ACTUAL.parent.name == "modules"
    else RUTA_ACTUAL.parent
)
DB_DIR = BASE_DIR / "database"
DB_PATH = DB_DIR / "sistema.db"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"


# --- FUNCIONES DE BASE DE DATOS Y CONFIGURACIÓN ---
def init_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS presupuestos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                cliente TEXT,
                telefono TEXT,
                total REAL,
                items_json TEXT,
                pdf_path TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracion (
                clave TEXT PRIMARY KEY,
                valor TEXT
            )
        """)
        conn.commit()
        ejecutar_sincronizacion_completa()


def guardar_config_db(clave, valor):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)", (clave, valor))
        conn.commit()
        ejecutar_sincronizacion_completa()


def obtener_config_db(clave):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
            res = cursor.fetchone()
            return res[0] if res else None
    except Exception:
        return None


def guardar_presupuesto_db(cliente, telefono, total, items, pdf_path):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
    items_json = json.dumps(items)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO presupuestos (fecha, cliente, telefono, total, items_json, pdf_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fecha_hoy, cliente, telefono, total, items_json, str(pdf_path)))
        conn.commit()
        ejecutar_sincronizacion_completa()


def obtener_historial_presupuestos():
    try:
        with get_connection() as conn:
            df = pd.read_sql_query(
                "SELECT id, fecha, cliente, telefono, total, pdf_path FROM presupuestos ORDER BY id DESC", 
                conn
            )
        return df
    except Exception:
        return pd.DataFrame()


def resolver_ruta_logo():
    """Busca automáticamente un logo válido en la base de datos, sesión o en la carpeta assets/."""
    # 1. Intentar de la base de datos o sesión[cite: 10]
    logo_path = obtener_config_db("logo_path") or st.session_state.get("logo_path_sesion", "")
    if logo_path and os.path.exists(logo_path):
        return logo_path

    # 2. Búsqueda automática en assets/ por nombres comunes o cualquier imagen disponible[cite: 10]
    nombres_preferidos = ["logo_empresa.png", "logo_cliente.jpeg", "logo_cliente.jpg", "logo.png", "logo.jpg"]
    for nombre in nombres_preferidos:
        posible = ASSETS_DIR / nombre
        if posible.exists():
            return str(posible)

    # 3. Buscar cualquier archivo de imagen en assets/[cite: 10]
    if ASSETS_DIR.exists():
        for archivo in ASSETS_DIR.glob("*.*"):
            if archivo.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                return str(archivo)

    return ""


# --- GENERADOR DE PDF ---
def generar_pdf_presupuesto(cliente, items, total, numero_presupuesto="0001", ruc_cliente="", filename="presupuesto.pdf"):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ruta_salida = OUTPUT_DIR / filename

    logo_path = resolver_ruta_logo()

    cfg = {
        "nombre": "GHV - Service",
        "rubro": "Servicios Informáticos & Soporte Técnico",
        "ruc": "2644016-4",
        "telefono": "+595 981 141010",
        "correo": "ghvservice@gmail.com",
        "direccion": "Mariano R. Alonso, Paraguay",
        "logo_path": logo_path,
        "titulo_pdf": "PRESUPUESTO DE SERVICIOS",
        "garantia_nota": "* Presupuesto válido por 5 días.\n* Precios sujetos a variación sin previo aviso."
    }

    doc = SimpleDocTemplate(str(ruta_salida), pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    empresa_style = ParagraphStyle('EmpresaStyle', parent=styles['Heading2'], fontSize=15, textColor=colors.HexColor("#0F172A"), leading=17)
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor("#475569"), leading=11)
    contacto_style = ParagraphStyle('ContactoStyle', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor("#64748B"), leading=10)
    desc_cell_style = ParagraphStyle('DescCell', parent=styles['Normal'], fontSize=9, leading=11)
    
    info_contacto_str = f"<b>RUC:</b> {cfg.get('ruc', '')} | <b>Tel:</b> {cfg.get('telefono', '')} | <b>Email:</b> {cfg.get('correo', '')} | {cfg.get('direccion', '')}"

    texto_header = [
        Paragraph(f"<b>{cfg.get('nombre', 'GHV - Service')}</b>", empresa_style),
        Spacer(1, 2),
        Paragraph(cfg.get('rubro', ''), sub_style),
        Spacer(1, 3),
        Paragraph(info_contacto_str, contacto_style)
    ]
    
    logo_archivo = cfg.get("logo_path")
    logo_agregado = False

    if logo_archivo and os.path.exists(logo_archivo):
        try:
            img = Image(logo_archivo, width=60, height=40)
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
            logo_agregado = True
        except Exception as e:
            print(f"Error al adjuntar logo en PDF: {e}")

    if not logo_agregado:
        for el in texto_header:
            story.append(el)
        
    # Línea divisoria[cite: 10]
    story.append(Spacer(1, 8))
    linea_divisoria = Table([[""]], colWidths=[540], rowHeights=[1])
    linea_divisoria.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#CBD5E1"))]))
    story.append(linea_divisoria)
    story.append(Spacer(1, 10))
    
    # Título y Número[cite: 10]
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor("#1E293B"))
    header_info_data = [
        [Paragraph(f"<b>{cfg.get('titulo_pdf', 'PRESUPUESTO').upper()}</b>", title_style),
         Paragraph(f"<b>N°:</b> {numero_presupuesto}", ParagraphStyle('NumStyle', parent=styles['Normal'], alignment=2, fontSize=11, textColor=colors.HexColor("#0F172A")))]
    ]
    t_header_info = Table(header_info_data, colWidths=[380, 160])
    t_header_info.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(t_header_info)
    story.append(Spacer(1, 8))
    
    # Cliente y Fecha[cite: 10]
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    ruc_txt = f" | <b>RUC/C.I.:</b> {ruc_cliente}" if ruc_cliente else ""
    cliente_info_str = f"<b>Fecha:</b> {fecha_hoy}&nbsp;&nbsp;|&nbsp;&nbsp;<b>Cliente:</b> {cliente}{ruc_txt}"
    story.append(Paragraph(cliente_info_str, styles['Normal']))
    story.append(Spacer(1, 12))

    # Tabla de Ítems[cite: 10]
    table_data = [["Descripción", "Cant.", "Precio Unit.", "Subtotal"]]
    for item in items:
        p_unit = f"Gs. {item['Precio Unitario']:,}".replace(",", ".")
        sub = f"Gs. {item['Subtotal']:,}".replace(",", ".")
        p_desc = Paragraph(item["Descripción"], desc_cell_style)
        table_data.append([p_desc, str(item["Cantidad"]), p_unit, sub])
    
    total_fmt = f"Gs. {total:,}".replace(",", ".")
    table_data.append(["", "", "TOTAL:", total_fmt])

    t = Table(table_data, colWidths=[270, 45, 115, 110])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (2,-1), (-1,-1), colors.HexColor("#E2E8F0")),
        ('TEXTCOLOR', (2,-1), (-1,-1), colors.HexColor("#0F172A")),
        ('FONTNAME', (2,-1), (-1,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (2,-1), (-1,-1), 6),
        ('TOPPADDING', (2,-1), (-1,-1), 6),
    ]))
    story.append(t)
    
    story.append(Spacer(1, 15))
    
    # Notas / Garantía[cite: 10]
    note_style = ParagraphStyle('NoteStyle', parent=styles['Italic'], fontSize=8, textColor=colors.HexColor("#64748B"), leading=10)
    garantia_texto = cfg.get("garantia_nota", "* Presupuesto válido por 5 días.\n* Precios sujetos a variación sin previo aviso.")
    for linea in garantia_texto.split('\n'):
        if linea.strip():
            story.append(Paragraph(linea.strip(), note_style))
            story.append(Spacer(1, 2))

    doc.build(story)
    return ruta_salida


# --- INTERFAZ STREAMLIT ---
def render():
    init_db()

    st.subheader("Generador rápido de cotizaciones y presupuestos")
    
    # --- SECCIÓN DE CONFIGURACIÓN DEL LOGO ---[cite: 10]
    with st.expander("⚙️ Configuración del Logo Corporativo", expanded=False):
        logo_actual = resolver_ruta_logo()
        if logo_actual and os.path.exists(logo_actual):
            st.success(f"Logo detectado actualmente (`{Path(logo_actual).name}`):")
            st.image(logo_actual, width=100)
        else:
            st.warning("⚠️ Todavía no hay ningún logo guardado. Subí uno abajo o colocalo en la carpeta assets.")
        
        archivo_subido = st.file_uploader("Subir nuevo logo (PNG / JPG)", type=["png", "jpg", "jpeg"])
        if archivo_subido is not None:
            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
            ruta_destino = ASSETS_DIR / "logo_empresa.png"
            with open(ruta_destino, "wb") as f:
                f.write(archivo_subido.getbuffer())
            
            guardar_config_db("logo_path", str(ruta_destino))
            st.session_state["logo_path_sesion"] = str(ruta_destino)
            st.success("¡Logo guardado exitosamente y listo para los próximos presupuestos!")
            st.rerun()

    st.markdown("---")

    if "lista_items" not in st.session_state:
        st.session_state.lista_items = []
    if "pdf_ready" not in st.session_state:
        st.session_state.pdf_ready = False

    col1, col2 = st.columns(2)
    with col1:
        nombre_cliente = st.text_input("Nombre / Empresa del Cliente", key="cliente_nombre")
    with col2:
        telefono_cliente = st.text_input("Número de WhatsApp del Cliente (ej: 595981xxxxxx)", key="cliente_telefono")

    st.markdown("#### Detalle del Presupuesto")
    col_desc, col_cant, col_precio = st.columns([3, 1, 1])
    with col_desc:
        descripcion = st.text_input("Descripción del servicio / repuesto", key="input_desc_temp")
    with col_cant:
        cantidad = st.number_input("Cant.", min_value=1, value=1, key="input_cant_temp")
    with col_precio:
        precio_unitario = st.number_input("Precio Unitario (Gs.)", min_value=0, step=5000, key="input_precio_temp")

    if st.button("➕ Agregar Ítem", use_container_width=True):
        if descripcion:
            subtotal = cantidad * precio_unitario
            st.session_state.lista_items.append({
                "Descripción": descripcion,
                "Cantidad": cantidad,
                "Precio Unitario": precio_unitario,
                "Subtotal": subtotal
            })
            st.session_state.pdf_ready = False
            st.success(f"Agregado: {descripcion}")
            st.rerun()
        else:
            st.warning("Por favor ingresá una descripción.")

    if len(st.session_state.lista_items) > 0:
        df = pd.DataFrame(st.session_state.lista_items)
        st.dataframe(df, use_container_width=True)
        
        total = sum(item["Subtotal"] for item in st.session_state.lista_items)
        total_fmt = f"{total:,}".replace(",", ".")
        st.markdown(f"### **Total: Gs. {total_fmt}**")
        
        if st.button("🗑️ Limpiar lista"):
            st.session_state.lista_items = []
            st.session_state.pdf_ready = False
            st.rerun()

    st.markdown("---")
    
    if st.button("🚀 Generar Presupuesto y PDF", type="primary", use_container_width=True):
        if not nombre_cliente:
            st.error("Por favor completá el nombre del cliente.")
        elif not st.session_state.lista_items:
            st.error("Agregá al menos un ítem al presupuesto.")
        else:
            total = sum(item["Subtotal"] for item in st.session_state.lista_items)
            total_fmt = f"{total:,}".replace(",", ".")
            
            num_presupuesto_str = datetime.now().strftime("%Y%m%d%H%M")[-6:]
            
            nombre_archivo_pdf = f"Presupuesto_{nombre_cliente.replace(' ', '_')}.pdf"
            ruta_pdf = generar_pdf_presupuesto(nombre_cliente, st.session_state.lista_items, total, numero_presupuesto=num_presupuesto_str, filename=nombre_archivo_pdf)
            guardar_presupuesto_db(nombre_cliente, telefono_cliente, total, st.session_state.lista_items, ruta_pdf)
            
            st.session_state.pdf_ready = True
            st.session_state.pdf_path = str(ruta_pdf)
            st.session_state.pdf_cliente = nombre_cliente
            st.session_state.pdf_total_fmt = total_fmt
            
            st.rerun()

    if st.session_state.get("pdf_ready") and os.path.exists(st.session_state.get("pdf_path", "")):
        st.success("¡Presupuesto y PDF listos y guardados en la base de datos!")
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            with open(st.session_state.pdf_path, "rb") as pdf_file:
                st.download_button(
                    label="📥 Descargar PDF",
                    data=pdf_file,
                    file_name=Path(st.session_state.pdf_path).name,
                    mime="application/pdf",
                    use_container_width=True
                )
            
        with col_btn2:
            tel_actual = st.session_state.get("cliente_telefono", "")
            clean_phone = re.sub(r'\D', '', tel_actual)
            
            if clean_phone:
                mensaje = f"Hola {st.session_state.pdf_cliente}, te adjunto el presupuesto solicitado de GHV - Service por un total de Gs. {st.session_state.pdf_total_fmt}."
                mensaje_url = urllib.parse.quote(mensaje)
                ws_url = f"https://wa.me/{clean_phone}?text={mensaje_url}"
                st.link_button("📲 Enviar por WhatsApp", ws_url, use_container_width=True)
            else:
                st.warning("⚠️ Escribí el número de WhatsApp arriba para habilitar el envío.")

    st.markdown("---")
    st.subheader("📋 Historial de Presupuestos Emitidos")
    df_historial = obtener_historial_presupuestos()
    if not df_historial.empty:
        df_historial["total"] = df_historial["total"].apply(lambda x: f"Gs. {x:,.0f}".replace(",", "."))
        st.dataframe(df_historial, use_container_width=True)
    else:
        st.info("Aún no hay presupuestos guardados en el historial.")