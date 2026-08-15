from pathlib import Path
from PIL import Image
import streamlit as st

# Determinación inteligente de rutas para mantener consistencia con los demás módulos
RUTA_ACTUAL = Path(__file__).resolve()
BASE_DIR = (
    RUTA_ACTUAL.parent.parent
    if RUTA_ACTUAL.parent.name == "modules"
    else RUTA_ACTUAL.parent
)
ASSETS_DIR = BASE_DIR / "assets"


def render():
    st.header("⚙️ Configuración del Negocio")
    st.caption("Personalizá los datos y el logotipo que figurarán en los PDF de presupuestos y órdenes.")
    st.markdown("---")

    # Asegurar inicialización segura del session_state si no existe
    if "config_negocio" not in st.session_state:
        st.session_state.config_negocio = {
            "nombre": "GHV - Service",
            "rubro": "Servicios Informáticos & Soporte Técnico",
            "ruc": "2644016-4",
            "telefono": "+595 981 141010",
            "correo": "ghvservice@gmail.com",
            "direccion": "Mariano R. Alonso, Paraguay",
            "logo_path": "logo_empresa.png",
            "titulo_pdf": "PRESUPUESTO SOLICITADO",
            "garantia_nota": "* Presupuesto válido por 15 días.\n* Precios sujetos a variación sin previo aviso."
        }

    cfg = st.session_state.config_negocio

    col1, col2 = st.columns(2, gap="medium")

    with col1:
        st.subheader("Datos Comerciales")
        cfg["nombre"] = st.text_input("Nombre de la Empresa", value=cfg.get("nombre", "GHV - Service"))
        cfg["rubro"] = st.text_input("Rubro / Eslogan", value=cfg.get("rubro", "Servicios Informáticos & Soporte Técnico"))
        cfg["ruc"] = st.text_input("RUC / CI", value=cfg.get("ruc", "2644016-4"))
        cfg["telefono"] = st.text_input("Teléfono de Contacto", value=cfg.get("telefono", "+595 981 141010"))
        cfg["correo"] = st.text_input("Correo Electrónico", value=cfg.get("correo", "ghvservice@gmail.com"))
        cfg["direccion"] = st.text_input("Dirección", value=cfg.get("direccion", "Mariano R. Alonso, Paraguay"))

    with col2:
        st.subheader("Imagen del Logo & Textos de PDF")
        
        # Asegurar que la carpeta assets/ exista
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        logo_path_default = ASSETS_DIR / "logo_empresa.png"
        
        logo_file = st.file_uploader(
            "Cargar / Cambiar Logo (JPG, JPEG, PNG, WEBP, BMP)", 
            type=["png", "jpg", "jpeg", "webp", "bmp"]
        )
        
        if logo_file is not None:
            try:
                img = Image.open(logo_file)
                
                # Preservar canal alfa o convertir a RGB estándar
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                    
                img.save(logo_path_default, "PNG")
                cfg["logo_path"] = str(logo_path_default)
                st.success("¡Logo guardado en assets/ y procesado correctamente!")
            except Exception as e:
                st.error(f"❌ Error al procesar la imagen: {e}")

        # Mostrar preview si existe la imagen físicamente en la carpeta assets/
        if logo_path_default.exists():
            st.image(str(logo_path_default), caption="Logo Actual Guardado", width=160)
            cfg["logo_path"] = str(logo_path_default)
        else:
            st.warning("⚠️ Aún no has guardado un logo permanente en la carpeta assets/.")

        st.markdown("---")
        cfg["titulo_pdf"] = st.text_input("Título en Documento PDF", value=cfg.get("titulo_pdf", "PRESUPUESTO SOLICITADO"))
        cfg["garantia_nota"] = st.text_area("Notas / Validez al pie del PDF", value=cfg.get("garantia_nota", "* Presupuesto válido por 15 días.\n* Precios sujetos a variación sin previo aviso."))

    if st.button("💾 Guardar Configuración", use_container_width=True, type="primary"):
        st.toast("Configuración guardada correctamente.", icon="✅")