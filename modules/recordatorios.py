from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import urllib.parse
import streamlit as st
import pandas as pd
from modules.database import get_connection  # Importa la conexión híbrida centralizada[cite: 6]
from sincronizador import ejecutar_sincronizacion_completa

# Determinación inteligente de rutas para sistema.db[cite: 6]
RUTA_ACTUAL = Path(__file__).resolve()
BASE_DIR = (
    RUTA_ACTUAL.parent.parent
    if RUTA_ACTUAL.parent.name == "modules"
    else RUTA_ACTUAL.parent
)
DB_DIR = BASE_DIR / "database"
DB_PATH = DB_DIR / "sistema.db"


def init_reminders_db():
    """Asegura que exista la tabla de recordatorios en la base de datos."""[cite: 6]
    DB_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()
        # Se añadió la columna sincronizado INTEGER DEFAULT 0
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recordatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_origen TEXT,
                cliente TEXT,
                telefono TEXT,
                equipo TEXT,
                servicio_realizado TEXT,
                fecha_ingreso TEXT,
                fecha_sugerida TEXT,
                estado_aviso TEXT DEFAULT 'Pendiente',
                sincronizado INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        ejecutar_sincronizacion_completa()


def sincronizar_ots_a_recordatorios():
    """Lee las órdenes de trabajo cerradas/ingresadas y genera recordatorios a 6 meses si no existen."""[cite: 6]
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Obtener OTs unidas con clientes[cite: 6]
            query = """
                SELECT ot.id_orden, ot.fecha_ingreso, ot.tipo_equipo, ot.marca_modelo, ot.falla_reportada,
                       c.nombre AS cliente_nombre, c.telefono AS cliente_tel
                FROM ordenes_trabajo ot
                JOIN clientes c ON ot.id_cliente = c.id
            """
            ots = cursor.execute(query).fetchall()

            for ot in ots:
                id_origen_str = f"OT-{ot['id_orden']:03d}"
                
                # Verificar si ya existe en la tabla recordatorios[cite: 6]
                existe = cursor.execute(
                    "SELECT 1 FROM recordatorios WHERE id_origen = ?", (id_origen_str,)
                ).fetchone()
                
                if not existe:
                    try:
                        fecha_ot = datetime.strptime(ot["fecha_ingreso"].split(" ")[0], "%Y-%m-%d")
                    except Exception:
                        fecha_ot = datetime.now()
                    
                    fecha_sugerida = fecha_ot + timedelta(days=180) # 6 meses por defecto[cite: 6]

                    # Se añadió sincronizado = 0 en el INSERT
                    cursor.execute("""
                        INSERT INTO recordatorios 
                        (id_origen, cliente, telefono, equipo, servicio_realizado, fecha_ingreso, fecha_sugerida, estado_aviso, sincronizado)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente', 0)
                    """, (
                        id_origen_str,
                        ot["cliente_nombre"],
                        ot["cliente_tel"] if ot["cliente_tel"] else "",
                        f"{ot['tipo_equipo']} - {ot['marca_modelo']}",
                        ot["falla_reportada"],
                        fecha_ot.strftime("%d/%m/%Y"),
                        fecha_sugerida.strftime("%d/%m/%Y")
                    ))
            conn.commit()
            ejecutar_sincronizacion_completa()
    except Exception as e:
        print(f"Error al sincronizar recordatorios: {e}")


def render():
    init_reminders_db()
    sincronizar_ots_a_recordatorios()

    st.header("🔔 Service Reminders & Seguimiento Posventa")
    st.caption("Fidelizá clientes enviando avisos de mantenimiento preventivo a los 6 meses de su service.")
    st.markdown("---")

    # 1. BOTÓN PARA AGREGAR RECORDATORIO MANUAL[cite: 6]
    with st.expander("➕ Agregar Recordatorio Manual (Sin OT previa)"):
        with st.form("form_rec_manual", clear_on_submit=True):
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                m_cliente = st.text_input("Nombre del Cliente")
                m_telefono = st.text_input("WhatsApp (ej: 595981xxxxxx)")
                m_equipo = st.text_input("Equipo / Instalación (ej: Limpieza Notebook Dell)")
            with col_m2:
                m_meses = st.selectbox("Recordar en:", [3, 6, 12], index=1, format_func=lambda x: f"{x} Meses")[cite: 6]
                m_servicio = st.text_input("Detalle del servicio preventivo", value="Mantenimiento preventivo general")
                
                submitted_manual = st.form_submit_button("📌 Registrar Recordatorio Manual", use_container_width=True)
                
                if submitted_manual:
                    if m_cliente and m_telefono:
                        f_sug = datetime.now() + timedelta(days=m_meses * 30)
                        try:
                            with get_connection() as conn:
                                cursor = conn.cursor()
                                # Se añadió sincronizado = 0 en el INSERT manual
                                cursor.execute("""
                                    INSERT INTO recordatorios 
                                    (id_origen, cliente, telefono, equipo, servicio_realizado, fecha_ingreso, fecha_sugerida, estado_aviso, sincronizado)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente', 0)
                                """, (
                                    f"MANUAL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                                    m_cliente,
                                    m_telefono,
                                    m_equipo,
                                    m_servicio,
                                    datetime.now().strftime("%d/%m/%Y"),
                                    f_sug.strftime("%d/%m/%Y")
                                ))
                                conn.commit()
                                ejecutar_sincronizacion_completa()
                            st.success("Recordatorio programado con éxito en la base de datos.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar recordatorio: {e}")
                    else:
                        st.warning("Completá al menos el nombre del cliente y su teléfono.")

    st.markdown("---")

    # 2. CARGAR RECORDATORIOS DESDE LA BD[cite: 6]
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            recordatorios = cursor.execute("SELECT * FROM recordatorios ORDER BY id DESC").fetchall()
    except Exception as e:
        st.error(f"No se pudieron cargar los recordatorios: {e}")
        recordatorios = []

    st.subheader("📋 Agenda de Mantenimientos Preventivos")

    if not recordatorios:
        st.info("No hay recordatorios pendientes. Se generan automáticamente al registrar Órdenes de Trabajo.")
        return

    # Métricas rápidas[cite: 6]
    pendientes = [r for r in recordatorios if r["estado_aviso"] == "Pendiente"]
    enviados = [r for r in recordatorios if r["estado_aviso"] == "Enviado"]

    col_stat1, col_stat2 = st.columns(2)
    col_stat1.metric("Pendientes de Avisar", len(pendientes))
    col_stat2.metric("Avisos Enviados", len(enviados))

    st.markdown("---")

    # Listado interactivo[cite: 6]
    for rec in recordatorios:
        badge = "🟢 ENVIADO" if rec["estado_aviso"] == "Enviado" else "⏳ PENDIENTE"
        
        with st.expander(f"{badge} | **{rec['cliente']}** — {rec['equipo']} (Sugerido: {rec['fecha_sugerida']})"):
            c_info, c_action = st.columns([3, 2], gap="medium")
            
            with c_info:
                st.write(f"**Origen / ID:** {rec['id_origen']}")
                st.write(f"**Cliente:** {rec['cliente']}")
                st.write(f"**Equipo:** {rec['equipo']}")
                st.write(f"**Último servicio registrado:** {rec['servicio_realizado']}")
                st.write(f"**Fecha del Service anterior:** {rec['fecha_ingreso']}")
                st.write(f"**Fecha sugerida de revisión:** {rec['fecha_sugerida']}")
            
            with c_action:
                st.markdown("#### Acciones de Fidelización")
                
                nombre_empresa = st.session_state.get("config_negocio", {}).get("nombre", "GHV - Service")
                
                # Plantilla de mensaje para WhatsApp[cite: 6]
                mensaje_wa = (
                    f"Hola {rec['cliente']}, te saludamos de *{nombre_empresa}*. 👋\n\n"
                    f"Te escribimos para recordarte que se cumplen 6 meses desde el último mantenimiento de tu *{rec['equipo']}*.\n\n"
                    f"💡 Para asegurar un óptimo rendimiento, evitar sobrecalentamiento y prolongar la vida útil del equipo, te recomendamos realizar una revisión preventiva.\n\n"
                    f"¿Te gustaría agendar una cita para esta semana?"
                )
                
                if rec['telefono']:
                    clean_phone = "".join(filter(str.isdigit, str(rec['telefono'])))
                    wa_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(mensaje_wa)}"
                    st.link_button("📲 Enviar Recordatorio por WA", wa_url, use_container_width=True)
                else:
                    st.warning("Sin número de WhatsApp registrado.")

                # Botones para cambiar estado en la BD[cite: 6]
                nuevo_estado = "Enviado" if rec["estado_aviso"] == "Pendiente" else "Pendiente"
                label_btn = "✅ Marcar como Notificado" if rec["estado_aviso"] == "Pendiente" else "🔄 Volver a Pendiente"
                
                if st.button(label_btn, key=f"btn_estado_{rec['id']}", use_container_width=True):
                    try:
                        with get_connection() as conn_upd:
                            # Se añadió sincronizado = 0 al actualizar el estado
                            conn_upd.execute(
                                "UPDATE recordatorios SET estado_aviso = ?, sincronizado = 0 WHERE id = ?",
                                (nuevo_estado, rec['id'])
                            )
                            conn_upd.commit()
                            ejecutar_sincronizacion_completa()
                        st.toast(f"Estado actualizado a '{nuevo_estado}'.", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al actualizar estado: {e}")