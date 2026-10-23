from datetime import datetime
import os
from pathlib import Path
import re
import urllib.parse

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st
import pandas as pd

# Determinación inteligente de rutas del proyecto
RUTA_ACTUAL = Path(__file__).resolve()
BASE_DIR = (
    RUTA_ACTUAL.parent.parent
    if RUTA_ACTUAL.parent.name == "modules"
    else RUTA_ACTUAL.parent
)
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"


def resolver_ruta_logo():
    """Busca automáticamente un logo válido en la carpeta assets/ o sesión."""
    logo_sesion = st.session_state.get("logo_path_sesion", "")
    if logo_sesion and os.path.exists(logo_sesion):
        return logo_sesion

    nombres_preferidos = ["logo_empresa.png", "logo_cliente.jpeg", "logo_cliente.jpg", "logo.png", "logo.jpg"]
    for nombre in nombres_preferidos:
        posible = ASSETS_DIR / nombre
        if posible.exists():
            return str(posible)

    if ASSETS_DIR.exists():
        for archivo in ASSETS_DIR.glob("*.*"):
            if archivo.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                return str(archivo)

    return ""


def generar_pdf_presupuesto(cliente, items, total, numero_presupuesto="0001", ruc_cliente="", filename="presupuesto.pdf"):
    """Genera el PDF del presupuesto en la carpeta output/ de forma 100% independiente."""
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
        
    story.append(Spacer(1, 8))
    linea_divisoria = Table([[""]], colWidths=[540], rowHeights=[1])
    linea_divisoria.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#CBD5E1"))]))
    story.append(linea_divisoria)
    story.append(Spacer(1, 10))
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor("#1E293B"))
    header_info_data = [
        [Paragraph(f"<b>{cfg.get('titulo_pdf', 'PRESUPUESTO').upper()}</b>", title_style),
         Paragraph(f"<b>N°:</b> {numero_presupuesto}", ParagraphStyle('NumStyle', parent=styles['Normal'], alignment=2, fontSize=11, textColor=colors.HexColor("#0F172A")))]
    ]
    t_header_info = Table(header_info_data, colWidths=[380, 160])
    t_header_info.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(t_header_info)
    story.append(Spacer(1, 8))
    
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    ruc_txt = f" | <b>RUC/C.I.:</b> {ruc_cliente}" if ruc_cliente else ""
    cliente_info_str = f"<b>Fecha:</b> {fecha_hoy}&nbsp;&nbsp;|&nbsp;&nbsp;<b>Cliente:</b> {cliente}{ruc_txt}"
    story.append(Paragraph(cliente_info_str, styles['Normal']))
    story.append(Spacer(1, 12))

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
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (2,-1), (-1,-1), colors.HexColor("#E2E8F0")),
        ('TEXTCOLOR', (2,-1), (-1,-1), colors.HexColor("#0F172A")),
        ('FONTNAME', (2,-1), (-1,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (2,-1), (-1,-1), 6),
        ('TOPPADDING', (2,-1), (-1,-1), 6),
    ]))
    story.append(t)
    
    story.append(Spacer(1, 15))
    
    note_style = ParagraphStyle('NoteStyle', parent=styles['Italic'], fontSize=8, textColor=colors.HexColor("#64748B"), leading=10)
    garantia_texto = cfg.get("garantia_nota", "* Presupuesto válido por 5 días.\n* Precios sujetos a variación sin previo aviso.")
    for linea in garantia_texto.split('\n'):
        if linea.strip():
            story.append(Paragraph(linea.strip(), note_style))
            story.append(Spacer(1, 2))

    doc.build(story)
    return ruta_salida


# --- INTERFAZ STREAMLIT (EXPRESS E INDEPENDIENTE) ---
def render():
    st.subheader("⚡ Presupuesto Express (PDF Independiente)")

    with st.expander("⚙️ Logo Corporativo (Opcional)", expanded=False):
        logo_actual = resolver_ruta_logo()
        if logo_actual and os.path.exists(logo_actual):
            st.success(f"Logo detectado actualmente (`{Path(logo_actual).name}`):")
            st.image(logo_actual, width=100)
        else:
            st.warning("⚠️ Sin logo en carpeta assets. Podés subir uno a continuación:")
        
        archivo_subido = st.file_uploader("Subir nuevo logo (PNG / JPG)", type=["png", "jpg", "jpeg"])
        if archivo_subido is not None:
            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
            ruta_destino = ASSETS_DIR / "logo_empresa.png"
            with open(ruta_destino, "wb") as f:
                f.write(archivo_subido.getbuffer())
            st.session_state["logo_path_sesion"] = str(ruta_destino)
            st.success("¡Logo guardado exitosamente!")
            st.rerun()

    st.markdown("---")

    # Inicializar memoria temporal de la sesión (sin BD)
    if "lista_items" not in st.session_state:
        st.session_state.lista_items = []
    if "pdf_ready" not in st.session_state:
        st.session_state.pdf_ready = False

    # Datos básicos del cliente
    col1, col2 = st.columns(2)
    with col1:
        nombre_cliente = st.text_input("Nombre / Empresa del Cliente", key="exp_nombre")
    with col2:
        telefono_cliente = st.text_input("Número de WhatsApp (ej: 595981xxxxxx)", key="exp_telefono")

    st.markdown("---")
    st.markdown("#### Detalle del Servicio")
    
    col_desc, col_cant, col_precio = st.columns([3, 1, 1])
    with col_desc:
        descripcion = st.text_input("Descripción del servicio / repuesto", key="exp_desc")
    with col_cant:
        cantidad = st.number_input("Cant.", min_value=1, value=1, key="exp_cant")
    with col_precio:
        precio_unitario = st.number_input("Precio Unitario (Gs.)", min_value=0, step=5000, key="exp_precio")

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
            st.success(f"¡Ítem agregado!")
            st.rerun()
        else:
            st.warning("Escribí una descripción primero.")

    # Tabla de ítems cargados
    if len(st.session_state.lista_items) > 0:
        st.markdown("---")
        st.markdown("#### Ítems cargados en esta cotización:")
        df = pd.DataFrame(st.session_state.lista_items)
        st.dataframe(df, use_container_width=True)
        
        total = sum(item["Subtotal"] for item in st.session_state.lista_items)
        total_fmt = f"{total:,}".replace(",", ".")
        st.markdown(f"### **Total: Gs. {total_fmt}**")

        c_gen1, c_gen2 = st.columns(2)
        with c_gen1:
            if st.button("🚀 Generar PDF Presupuesto", use_container_width=True, type="primary"):
                if not nombre_cliente:
                    st.error("Por favor completá el nombre del cliente arriba.")
                else:
                    num_presupuesto_str = datetime.now().strftime("%Y%m%d%H%M")[-6:]
                    nombre_archivo_pdf = f"Presupuesto_{nombre_cliente.replace(' ', '_')}.pdf"
                    
                    ruta_pdf = generar_pdf_presupuesto(
                        nombre_cliente, 
                        st.session_state.lista_items, 
                        total, 
                        numero_presupuesto=num_presupuesto_str, 
                        filename=nombre_archivo_pdf
                    )
                    
                    st.session_state.pdf_ready = True
                    st.session_state.pdf_path = str(ruta_pdf)
                    st.session_state.pdf_cliente = nombre_cliente
                    st.session_state.pdf_total_fmt = total_fmt
                    st.rerun()

        with c_gen2:
            if st.button("🗑️ Limpiar Todo", use_container_width=True):
                st.session_state.lista_items = []
                st.session_state.pdf_ready = False
                st.rerun()

    st.markdown("---")

    # Zona de Descarga / Enviar WhatsApp
    if st.session_state.get("pdf_ready") and os.path.exists(st.session_state.get("pdf_path", "")):
        st.success("¡PDF generado exitosamente!")
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
            tel_actual = st.session_state.get("exp_telefono", "")
            clean_phone = re.sub(r'\D', '', tel_actual)
            
            if clean_phone:
                mensaje = f"Hola {st.session_state.pdf_cliente}, te adjunto el presupuesto solicitado de GHV - Service por un total de Gs. {st.session_state.pdf_total_fmt}."
                mensaje_url = urllib.parse.quote(mensaje)
                ws_url = f"https://wa.me/{clean_phone}?text={mensaje_url}"
                st.link_button("📲 Enviar mensaje por WhatsApp", ws_url)
            else:
                st.info("💡 Colocá el WhatsApp del cliente arriba si querés enviarle el enlace directo.")