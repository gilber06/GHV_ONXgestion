from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Determinación inteligente del directorio raíz del proyecto
RUTA_ACTUAL = Path(__file__).resolve()
BASE_DIR = (
    RUTA_ACTUAL.parent.parent
    if RUTA_ACTUAL.parent.name == "modules"
    else RUTA_ACTUAL.parent
)

# Definición de carpetas assets/ y output/
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"


def resolver_ruta_logo(nombre_logo):
    """Busca la imagen del logo en la carpeta assets/ si no es una ruta absoluta."""
    if not nombre_logo:
        return None

    path_logo = Path(nombre_logo)
    if path_logo.is_absolute() and path_logo.exists():
        return path_logo

    # Intentar buscar en la carpeta assets/
    posible_asset = ASSETS_DIR / nombre_logo
    if posible_asset.exists():
        return posible_asset

    # Búsqueda secundaria por extensión
    for ext in [".png", ".PNG", ".jpeg", ".jpg"]:
        archivo_alt = ASSETS_DIR / f"{path_logo.stem}{ext}"
        if archivo_alt.exists():
            return archivo_alt

    return None


def generar_pdf_presupuesto(nombre_archivo, datos):
    """
    Genera un archivo PDF de presupuesto formal y retorna la ruta completa (Path) del archivo.
    """
    # Asegurar que la carpeta output/ exista
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ruta_salida = OUTPUT_DIR / nombre_archivo

    doc = SimpleDocTemplate(
        str(ruta_salida),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    story = []

    # --- Estilos ---
    styles = getSampleStyleSheet()

    style_subtitulo = ParagraphStyle(
        "Subtitulo",
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#555555"),
    )
    style_titulo_doc = ParagraphStyle(
        "TituloDoc",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#1E2A38"),
    )
    style_info = ParagraphStyle(
        "Info",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1E2A38"),
    )

    style_th = ParagraphStyle(
        "TH",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#1E2A38"),
    )
    style_td = ParagraphStyle(
        "TD",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#222222"),
    )
    style_td_center = ParagraphStyle(
        "TDC",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=1,
        textColor=colors.HexColor("#222222"),
    )
    style_total_label = ParagraphStyle(
        "TotalLabel",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=2,
        textColor=colors.HexColor("#1E2A38"),
    )
    style_total_val = ParagraphStyle(
        "TotalVal",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#1E2A38"),
    )

    style_legales = ParagraphStyle(
        "Legales",
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#777777"),
    )

    # --- Encabezado: Logo e Info Empresa ---
    empresa = datos.get("empresa", "GHV - Service")
    rubro = datos.get("rubro", "Servicios Informáticos & Soporte Técnico")
    ruc = datos.get("ruc", "")
    telefono = datos.get("telefono", "")
    email = datos.get("email", "")
    ubicacion = datos.get("ubicacion", "")

    info_empresa_text = f"""
    <b>{empresa}</b><br/>
    <font color="#555555">{rubro}</font><br/>
    <font color="#666666" size="8"><b>RUC:</b> {ruc} | <b>Tel:</b> {telefono} | <b>Email:</b> {email}<br/>{ubicacion}</font>
    """

    # Carga segura del logo
    ruta_logo_final = resolver_ruta_logo(datos.get("logo_path"))
    if ruta_logo_final:
        try:
            logo_img = Image(str(ruta_logo_final), width=1.5 * inch, height=0.75 * inch)
        except Exception:
            logo_img = Paragraph("", styles["Normal"])
    else:
        logo_img = Paragraph("", styles["Normal"])

    p_empresa = Paragraph(info_empresa_text, style_subtitulo)

    header_table = Table([[logo_img, p_empresa]], colWidths=[1.6 * inch, 5.6 * inch])
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 15))

    # --- Título y Datos del Cliente / Fecha ---
    story.append(Paragraph("<b>PRESUPUESTO SOLICITADO</b>", style_titulo_doc))
    story.append(Spacer(1, 8))

    fecha = datos.get("fecha", "")
    cliente = datos.get("cliente", "Cliente General")
    info_cliente_text = f"<b>Fecha:</b> {fecha} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Cliente:</b> {cliente}"
    story.append(Paragraph(info_cliente_text, style_info))
    story.append(Spacer(1, 15))

    # --- Tabla de Ítems ---
    table_data = [[
        Paragraph("Descripción", style_th),
        Paragraph("Cant.", style_th),
        Paragraph("Precio Unit.", style_th),
        Paragraph("Subtotal", style_th),
    ]]

    for item in datos.get("items", []):
        table_data.append([
            Paragraph(str(item.get("descripcion", "")), style_td),
            Paragraph(str(item.get("cantidad", 1)), style_td_center),
            Paragraph(str(item.get("precio_unitario", "")), style_td),
            Paragraph(str(item.get("subtotal", "")), style_td),
        ])

    # Fila de Total
    table_data.append([
        Paragraph("", style_td),
        Paragraph("", style_td),
        Paragraph("TOTAL:", style_total_label),
        Paragraph(str(datos.get("total", "")), style_total_val),
    ])

    tabla_presupuesto = Table(
        table_data, colWidths=[3.8 * inch, 0.7 * inch, 1.35 * inch, 1.35 * inch]
    )
    tabla_presupuesto.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF3F8")),
            ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#D1D5DB")),
            ("LINEABOVE", (2, -1), (3, -1), 1, colors.HexColor("#1E2A38")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(tabla_presupuesto)
    story.append(Spacer(1, 20))

    # --- Notas Legales / Condiciones ---
    condiciones = datos.get("condiciones", [
        "* Presupuesto válido por 5 días.",
        "* Precios sujetos a variación sin previo aviso."
    ])
    for nota in condiciones:
        story.append(Paragraph(nota, style_legales))
        story.append(Spacer(1, 2))

    # Construir PDF
    doc.build(story)
    print(f"PDF generado correctamente en: {ruta_salida}")

    # Retorna la ruta para ser consumida externamente
    return ruta_salida


# --- Prueba manual de ejecución ---
if __name__ == "__main__":
    datos_presupuesto = {
        "logo_path": "logo_cliente.jpeg",
        "empresa": "GHV - Service",
        "rubro": "Servicios Informáticos & Soporte Técnico",
        "ruc": "2644016-4",
        "telefono": "+595 981 141010",
        "email": "ghvservice@gmail.com",
        "ubicacion": "Mariano R. Alonso, Paraguay",
        "fecha": "12/08/2026",
        "cliente": "CODIG SA",
        "items": [{
            "descripcion": "REPARACION DE SENSOR DE IMPRESION + MANTENIMIENTO",
            "cantidad": 1,
            "precio_unitario": "Gs. 350.000",
            "subtotal": "Gs. 350.000",
        }],
        "total": "Gs. 350.000",
    }

    generar_pdf_presupuesto("presupuesto_CODIG_SA.pdf", datos_presupuesto)