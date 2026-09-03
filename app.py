from sincronizador import ejecutar_sincronizacion_completa
import os
import sqlite3
import time
import urllib.parse
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import streamlit as st

# ----------------------------------------------------
# IMPORTACIÓN DE MÓDULOS DE LA CARPETA /modules
# ----------------------------------------------------
try:
    from modules import presupuestos
except ImportError:
    presupuestos = None

try:
    from modules import recordatorios
except ImportError:
    recordatorios = None

try:
    from modules import mi_negocio
except ImportError:
    mi_negocio = None

try:
    import plotly.express as px
except ImportError:
    st.error("Por favor, instala plotly ejecutando: pip install plotly")

# ==========================================
# 1. CONFIGURACIÓN Y PARCHE DE BASE DE DATOS
# ==========================================
st.set_page_config(
    page_title="GHV - Service & OnXpert", layout="wide", page_icon="📈"
)

# Definición de la ruta robusta a la base de datos dentro de la carpeta 'database'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "sistema.db")


def inicializar_db():
    # Asegurar que la carpeta database exista físicamente
    if not os.path.exists(os.path.join(BASE_DIR, "database")):
        os.makedirs(os.path.join(BASE_DIR, "database"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Creación de tablas base
    cursor.execute("""CREATE TABLE IF NOT EXISTS clientes 
                    (id INTEGER PRIMARY KEY, nombre TEXT, apodo TEXT, telefono TEXT, es_companero BOOLEAN)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS negocios 
                    (id INTEGER PRIMARY KEY, nombre TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS ordenes 
                    (id INTEGER PRIMARY KEY, negocio_id INTEGER, cliente_id INTEGER, 
                     descripcion TEXT, fecha_ingreso TEXT, monto_total REAL, 
                     costo_insumos REAL DEFAULT 0, estado TEXT,
                     FOREIGN KEY(negocio_id) REFERENCES negocios(id))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS pagos 
                    (id INTEGER PRIMARY KEY, orden_id INTEGER, monto_cuota REAL, 
                     fecha_vencimiento TEXT, estado_pago TEXT)""")

    cursor.execute("PRAGMA table_info(ordenes)")
    columnas = [info[1] for info in cursor.fetchall()]
    if "costo_insumos" not in columnas:
        cursor.execute("ALTER TABLE ordenes ADD COLUMN costo_insumos REAL DEFAULT 0")

    cursor.execute("SELECT COUNT(*) FROM negocios")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO negocios (id, nombre, sincronizado) VALUES (?,?,0)",
            [(1, "GHV Service"), (2, "OnXpert Software")],
        )

    cursor.execute("""CREATE TABLE IF NOT EXISTS ventas_articulos 
                    (id INTEGER PRIMARY KEY, cliente_id INTEGER, producto TEXT, 
                     tipo_pago TEXT, monto_total REAL, costo_adquisicion REAL, 
                     fecha_venta TEXT)""")

    cursor.execute("PRAGMA table_info(clientes)")
    cols_c = [info[1] for info in cursor.fetchall()]
    if "ruc_ci" not in cols_c:
        cursor.execute("ALTER TABLE clientes ADD COLUMN ruc_ci TEXT")
    if "activo" not in cols_c:
        cursor.execute("ALTER TABLE clientes ADD COLUMN activo INTEGER DEFAULT 1")

    cursor.execute("PRAGMA table_info(pagos)")
    cols_p = [info[1] for info in cursor.fetchall()]
    if "notas" not in cols_p:
        cursor.execute("ALTER TABLE pagos ADD COLUMN notas TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_eliminacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orden_id INTEGER,
            cliente TEXT,
            monto REAL,
            detalle TEXT,
            fecha_eliminacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""CREATE TABLE IF NOT EXISTS productos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     categoria TEXT, 
                     marca TEXT, 
                     capacidad_especificacion TEXT, 
                     stock INTEGER DEFAULT 0, 
                     precio_costo REAL DEFAULT 0, 
                     precio_venta REAL DEFAULT 0)""")

    # TABLA PARA RECEPCIÓN DE EQUIPOS / TALLER
    cursor.execute("""CREATE TABLE IF NOT EXISTS ordenes_trabajo (
                        id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
                        id_cliente INTEGER NOT NULL,
                        tipo_equipo TEXT NOT NULL,
                        marca_modelo TEXT NOT NULL,
                        numero_serie TEXT,
                        accesorios TEXT,
                        falla_reportada TEXT NOT NULL,
                        diagnostico_tecnico TEXT,
                        monto_presupuesto REAL DEFAULT 0.00,
                        estado TEXT DEFAULT 'Pendiente de Revisión',
                        fecha_ingreso DATETIME DEFAULT CURRENT_TIMESTAMP,
                        fecha_modificacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(id_cliente) REFERENCES clientes(id)
                    )""")

    conn.commit()
    conn.close()  # Cerramos la conexión limpia aquí

# 1. PRIMERO: Creamos la estructura de la base de datos y tablas
inicializar_db()

# 2. SEGUNDO: Sincronización inicial al abrir la app (solo una vez por sesión)
if "sincronizado_inicial" not in st.session_state:
    try:
        ejecutar_sincronizacion_completa()
        st.session_state["sincronizado_inicial"] = True
    except Exception as e:
        st.error(f"Error en sincronización inicial: {e}")

# --- BOTÓN DE SINCRONIZACIÓN MANUAL (SIDEBAR) ---
st.sidebar.markdown("---")
st.sidebar.subheader("☁️ Control de Nube")

if st.sidebar.button("🔄 Sincronizar Ahora"):
    with st.sidebar.spinner('Conectando con Supabase...'):
        try:
            ejecutar_sincronizacion_completa()
            st.sidebar.success("¡Sincronización completa!")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
            st.sidebar.write("Verifica tu conexión a internet o la clave de Supabase.")

# ==========================================
# 2. FUNCIONES DE LÓGICA DE NEGOCIO
# ==========================================


def registrar_venta_onxpert(
    cliente,
    empresa,
    telefono,
    desc,
    monto_soft,
    cuotas_soft,
    monto_memb,
    cuotas_memb,
    fecha_manual,
):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR IGNORE INTO clientes (nombre, apodo, telefono, sincronizado) VALUES (?,?,?,0)",
      (cliente, empresa, telefono),
  )
  cursor.execute(
      "UPDATE clientes SET apodo = ?, telefono = ?, sincronizado = 0 WHERE nombre = ?",
      (empresa, telefono, cliente),
  )
  cursor.execute("SELECT id FROM clientes WHERE nombre = ?", (cliente,))
  cliente_id = cursor.fetchone()[0]

  monto_total_op = monto_soft + (monto_memb * cuotas_memb)
  cursor.execute(
      """
        INSERT INTO ordenes (negocio_id, cliente_id, descripcion, fecha_ingreso, monto_total, costo_insumos, estado, sincronizado) 
        VALUES (2, ?, ?, ?, ?, 0, 'Activo', 0)
    """,
      (
          cliente_id,
          desc,
          fecha_manual.strftime("%Y-%m-%d"),
          monto_total_op,
      ),
  )

  orden_id = cursor.lastrowid

  # 1. Registro de Cuotas del Software (Implementación)
  if monto_soft > 0:
    if cuotas_soft == 1:
      cursor.execute(
          """
                INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado) 
                VALUES (?, ?, ?, 'Pendiente', 'SOFTWARE / IMPLEMENTACIÓN', 0)
            """,
          (orden_id, monto_soft, fecha_manual.strftime("%Y-%m-%d")),
      )
    else:
      monto_cuota_soft = monto_soft / cuotas_soft
      for i in range(cuotas_soft):
        venc_soft = fecha_manual + relativedelta(months=i)
        cursor.execute(
            """
                    INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado) 
                    VALUES (?, ?, ?, 'Pendiente', ?, 0)
                """,
            (
                orden_id,
                monto_cuota_soft,
                venc_soft.strftime("%Y-%m-%d"),
                f"SOFTWARE CUOTA {i+1}/{cuotas_soft}",
            ),
        )

  # 2. Registro de Cuotas de Membresía / Mantenimiento
  if monto_memb > 0 and cuotas_memb > 0:
    for i in range(cuotas_memb):
      venc_memb = fecha_manual + relativedelta(months=i)
      cursor.execute(
          """
                INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado) 
                VALUES (?, ?, ?, 'Pendiente', ?, 0)
            """,
          (
              orden_id,
              monto_memb,
              venc_memb.strftime("%Y-%m-%d"),
              f"MEMBRESÍA MES {i+1}/{cuotas_memb}",
          ),
      )

  conn.commit()
  ejecutar_sincronizacion_completa()
  conn.close()


def actualizar_datos_cliente(
    id_cliente, nuevo_nombre, nueva_empresa, nuevo_telefono, nuevo_ruc
):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      """UPDATE clientes 
                      SET nombre = ?, apodo = ?, telefono = ?, ruc_ci = ?, sincronizado = 0 
                      WHERE id = ?""",
      (nuevo_nombre, nueva_empresa, nuevo_telefono, nuevo_ruc, id_cliente),
  )
  conn.commit()
  ejecutar_sincronizacion_completa()
  conn.close()


def cambiar_estado_cliente(id_cliente, activo=True):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  estado = 1 if activo else 0
  cursor.execute(
      "UPDATE clientes SET activo = ?, sincronizado = 0 WHERE id = ?", (estado, id_cliente)
  )
  conn.commit()
  ejecutar_sincronizacion_completa()
  conn.close()


# Helper universal para ejecutar el render de cualquier módulo importado
def ejecutar_render_modulo(modulo, nombre_modulo="El módulo"):
  if modulo is None:
    st.warning(
        f"⚠️ No se encontró el archivo `modules/{nombre_modulo.lower()}.py` o"
        " faltan dependencias."
    )
    return
  for func_name in ["render", "main", "app", "mostrar"]:
    if hasattr(modulo, func_name):
      getattr(modulo, func_name)()
      return
  st.info(f"El módulo `{nombre_modulo}` está cargado correctamente.")


# ==========================================
# 3. NAVEGACIÓN Y BARRA LATERAL
# ==========================================

st.sidebar.title("GHV - Service & OnXpert")

st.sidebar.markdown(
    """
    <style>
        .sidebar-footer {
            position: fixed;
            bottom: 15px;
            width: 15rem;
            text-align: center;
            font-size: 13px;
            color: #555555;
            font-family: 'Segoe UI', sans-serif;
            z-index: 100;
        }
    </style>
    <div class="sidebar-footer">
        <span style="opacity: 0.7;">Desarrollado por</span><br>
        <b style="color: #000000; letter-spacing: 1px;">OnXpert™ Software 2026</b>
    </div>
    """,
    unsafe_allow_html=True,
)

menu = [
    "📊 Dashboard",
    "🛠️ Recepción de Equipos (Taller)",
    "👥 Gestión de Clientes",
    "🛒 Nueva Venta / Servicio",
    "🗓️ Cobros Pendientes",
    "📝 Órdenes de Trabajo",
    "📄 Presupuestos Express",
    "🔔 Recordatorios",
    "✅ Historial de Cobrados",
    "📈 Reportes Avanzados",
    "📦 Inventario / Stock",
    "⚙️ Configuración / Mi Negocio",
]
choice = st.sidebar.selectbox("Ir a:", menu)

conn = sqlite3.connect(DB_PATH)

# ==========================================
# 4. VISTA: DASHBOARD
# ==========================================
if choice == "📊 Dashboard":
  st.title("Resumen Ejecutivo")
  c1, c2, c3, c4 = st.columns(4)

  res_pend = pd.read_sql_query(
      "SELECT SUM(monto_cuota) FROM pagos WHERE estado_pago='Pendiente'", conn
  ).iloc[0, 0]
  pend = 0 if pd.isna(res_pend) else res_pend

  res_coba = pd.read_sql_query(
      "SELECT SUM(monto_cuota) FROM pagos WHERE estado_pago='Pagado'", conn
  ).iloc[0, 0]
  coba = 0 if pd.isna(res_coba) else res_coba

  res_tp = pd.read_sql_query(
      "SELECT SUM(monto_cuota) FROM pagos", conn
  ).iloc[0, 0]
  total_pagos_db = 0 if pd.isna(res_tp) else res_tp

  res_tc = pd.read_sql_query(
      "SELECT SUM(costo_insumos) FROM ordenes", conn
  ).iloc[0, 0]
  total_costos_db = 0 if pd.isna(res_tc) else res_tc

  utilidad_proyectada = total_pagos_db - total_costos_db

  c1.metric("Por Cobrar", f"{int(pend):,} Gs.".replace(",", "."))
  c2.metric("Ya Cobrado", f"{int(coba):,} Gs.".replace(",", "."))
  c3.metric(
      "Utilidad Neta Proyectada",
      f"{int(utilidad_proyectada):,} Gs.".replace(",", "."),
  )
  c4.metric(
      "Órdenes Activas",
      len(
          pd.read_sql_query(
              "SELECT id FROM ordenes WHERE estado != 'Entregado'", conn
          )
      ),
  )

  st.divider()

  st.subheader("📈 Ingresos Reales por Mes (Histórico)")
  df_hist = pd.read_sql_query(
      """
        SELECT strftime('%Y-%m', fecha_vencimiento) as Mes, SUM(monto_cuota) as Total 
        FROM pagos WHERE estado_pago = 'Pagado' GROUP BY Mes ORDER BY Mes
    """,
      conn,
  )
  if not df_hist.empty:
    fig_h = px.bar(
        df_hist,
        x="Mes",
        y="Total",
        title="Dinero Cobrado por Mes",
        color_discrete_sequence=["#2ecc71"],
    )
    st.plotly_chart(fig_h, use_container_width=True)
  else:
    st.info(
        "Aún no hay cobros marcados como 'Pagado' para mostrar en el historial."
    )

  st.subheader("🗓️ Proyección de Cobros Futuros")
  df_mes = pd.read_sql_query(
      """
        SELECT strftime('%Y-%m', fecha_vencimiento) as Mes, SUM(monto_cuota) as Total 
        FROM pagos WHERE estado_pago = 'Pendiente' GROUP BY Mes ORDER BY Mes
    """,
      conn,
  )
  if not df_mes.empty:
    fig = px.line(
        df_mes,
        x="Mes",
        y="Total",
        title="Flujo de Caja Pendiente",
        markers=True,
    )
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 5. VISTA: RECEPCIÓN DE EQUIPOS (TALLER)
# ==========================================
elif choice == "🛠️ Recepción de Equipos (Taller)":
  st.title("Gestión de Taller y Recepción de Equipos")

  tab_rec1, tab_rec2, tab_rec3 = st.tabs([
      "📥 Ingresar Nuevo Equipo",
      "📋 Equipos en Taller",
      "💬 Enviar Comprobante / Aviso",
  ])

  df_clientes_rec = pd.read_sql_query(
      "SELECT id, apodo || ' - ' || nombre as cliente_display FROM clientes"
      " WHERE activo = 1",
      conn,
  )

  with tab_rec1:
    st.subheader("Formulario de Entrada de Equipos (Recepción)")
    if df_clientes_rec.empty:
      st.warning(
          "⚠️ Primero debes registrar un cliente en 'Gestión de Clientes'."
      )
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
              ejecutar_sincronizacion_completa()
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
            "⚡ Si pasa a 'Aprobado' o 'En Producción', generar cobro pendiente"
            " en Cartera de Clientes",
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
                  f"REPARACIÓN/TALLER: {datos_ot_taller['Marca / Modelo']} (OT"
                  f" #{id_ot_actual})"
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
                                INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
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
            ejecutar_sincronizacion_completa()
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

# ==========================================
# 6. VISTA: COBROS PENDIENTES
# ==========================================
elif choice == "🗓️ Cobros Pendientes":
  st.title("Control de Cobros")

  df_p = pd.read_sql_query(
      """
        SELECT p.id as ID, 
               COALESCE(n.nombre, 'Sin Negocio') as Negocio,
               COALESCE(NULLIF(c.apodo, ''), c.nombre) as Empresa,
               c.nombre as Contacto,
               p.monto_cuota as Monto,
               p.fecha_vencimiento as Vence,
               o.descripcion as Detalle,
               c.telefono as Telefono, 
               p.notas as Notas
        FROM pagos p
        JOIN ordenes o ON p.orden_id = o.id
        JOIN clientes c ON o.cliente_id = c.id
        LEFT JOIN negocios n ON o.negocio_id = n.id
        WHERE p.estado_pago = 'Pendiente'
        ORDER BY p.fecha_vencimiento ASC
    """,
      conn,
  )

  if not df_p.empty:
    clientes_con_deuda = df_p["Empresa"].unique()

    for empresa in clientes_con_deuda:
      pagos_cliente = df_p[df_p["Empresa"] == empresa]
      total_deuda_cliente = pagos_cliente["Monto"].sum()

      with st.expander(
          f"👤 {empresa} - (Total Pendiente:"
          f" {int(total_deuda_cliente):,} Gs.)".replace(",", ".")
      ):
        pagos_vista = pagos_cliente.copy()
        pagos_vista["Notas"] = pagos_vista["Notas"].fillna("")

        def resaltar_vencidos(row):
          vence = datetime.strptime(str(row["Vence"]), "%Y-%m-%d").date()
          hoy = datetime.now().date()
          if vence <= hoy:
            return [
                "background-color: #ffcccc; color: black; font-weight: bold"
            ] * len(row)
          return [""] * len(row)

        df_estilado = (
            pagos_vista[["ID", "Vence", "Monto", "Detalle", "Notas"]]
            .style.apply(resaltar_vencidos, axis=1)
            .format({"Monto": lambda x: f"{int(x):,} Gs.".replace(",", ".")})
        )
        st.dataframe(df_estilado, use_container_width=True, hide_index=True)

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
                  "UPDATE pagos SET estado_pago = 'Pagado', sincronizado = 0 WHERE id = ?",
                  (pago_id,),
              )
              conn.commit()
              ejecutar_sincronizacion_completa()
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
              with sqlite3.connect(DB_PATH) as conn_reprog:
                conn_reprog.execute(
                    """
                                    UPDATE pagos 
                                    SET fecha_vencimiento = ?, notas = ?, sincronizado = 0 
                                    WHERE id = ?
                                """,
                    (
                        nueva_fecha.strftime("%Y-%m-%d"),
                        nota_reprog.upper(),
                        pago_id,
                    ),
                )
                conn_reprog.commit()
                ejecutar_sincronizacion_completa()
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

            monto_actual_pago = pagos_cliente[
                pagos_cliente["ID"] == pago_id
            ]["Monto"].values[0]
            monto_nueva_cuota = monto_actual_pago / num_partes
            st.caption(
                f"💡 Se generarán **{num_partes} cuotas de"
                f" {int(monto_nueva_cuota):,} Gs.**".replace(",", ".")
            )

            if st.button(
                "✂️ Confirmar División de Pago",
                key=f"btn_dividir_{empresa}_{pago_id}",
            ):
              with sqlite3.connect(DB_PATH) as conn_div:
                cursor_div = conn_div.cursor()
                cursor_div.execute(
                    "SELECT orden_id, notas FROM pagos WHERE id = ?", (pago_id,)
                )
                ord_id, nota_orig = cursor_div.fetchone()
                nota_orig_txt = nota_orig if nota_orig else "CUOTA"

                cursor_div.execute("DELETE FROM pagos WHERE id = ?", (pago_id,))

                for i in range(int(num_partes)):
                  vence_div = fecha_primera + relativedelta(months=i)
                  nueva_nota = f"{nota_orig_txt} (PARTE {i+1}/{int(num_partes)})"
                  cursor_div.execute(
                      """
                                        INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
                                        VALUES (?, ?, ?, 'Pendiente', ?, 0)
                                    """,
                      (
                          ord_id,
                          monto_nueva_cuota,
                          vence_div.strftime("%Y-%m-%d"),
                          nueva_nota,
                      ),
                  )

                conn_div.commit()
                ejecutar_sincronizacion_completa()
              st.success(
                  f"✅ ¡Pago divido exitosamente en {num_partes} cuotas!"
              )
              time.sleep(1)
              st.rerun()

        with col_btn2:
          r_wa = pagos_cliente[pagos_cliente["ID"] == pago_id].iloc[0]
          monto_wa = f"{int(r_wa['Monto']):,}".replace(",", ".")

          msg = (
              f"Estimado cliente de {r_wa['Negocio']},\n\n"
              "Le enviamos un recordatorio de su cuota pendiente:\n"
              f"📌 Detalle: {r_wa['Detalle']}\n"
              f"💰 Monto: {monto_wa} Gs.\n"
              f"📅 Vencimiento: {r_wa['Vence']}\n\n"
              "¡Saludos!"
          )

          st.markdown("---")
          st.caption("🔍 Previsualización del mensaje:")
          st.info(msg)

          tel = str(r_wa["Telefono"]).replace(" ", "").replace("+", "")
          link = f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"
          st.markdown(
              f"[📲 Enviar WhatsApp a {empresa}]({link})",
              unsafe_allow_html=True,
          )

    total_general = df_p["Monto"].sum()
    st.divider()
    st.metric(
        "Total General a Cobrar", f"{int(total_general):,} Gs.".replace(",", ".")
    )

  else:
    st.info("No hay cobros pendientes por el momento.")

  st.markdown("---")
  with st.expander("⚠️ Zona de Limpieza (Solo errores de carga)"):
    id_borrar = st.number_input("ID del pago a eliminar", min_value=0, step=1)
    if st.button("🗑️ Eliminar Permanentemente"):
      conn.execute("DELETE FROM pagos WHERE id = ?", (id_borrar,))
      conn.commit()
      ejecutar_sincronizacion_completa()
      st.rerun()

# ==========================================
# 7. VISTA: GESTIÓN DE CLIENTES
# ==========================================
elif choice == "👥 Gestión de Clientes":
  st.title("Gestión Centralizada de Clientes")

  tab1, tab2, tab3 = st.tabs(
      ["➕ Registrar Nuevo", "📝 Ver / Editar", "🚫 Dar de Baja"]
  )

  with tab1:
    st.subheader("Cargar Cliente al Sistema")
    with st.form("nuevo_cliente_unificado", clear_on_submit=True):
      col1, col2 = st.columns(2)
      with col1:
        nombre = st.text_input("Nombre y Apellido / Razón Social")
        empresa = st.text_input("Empresa / Apodo (Ej: La Hornalla)")
      with col2:
        telefono = st.text_input("Teléfono / WhatsApp")
        ruc = st.text_input("RUC o CI")

      boton_guardar = st.form_submit_button("Dar de Alta Cliente")

    if boton_guardar:
      if not nombre:
        st.error("⚠️ El campo 'Nombre y Apellido / Razón Social' es obligatorio.")
      else:
        nombre_norm = nombre.strip().upper()
        empresa_norm = empresa.strip().upper() if empresa else ""
        ruc_norm = ruc.strip().upper() if ruc else ""

        with sqlite3.connect(DB_PATH) as conn_local:
          cursor_local = conn_local.cursor()
          cursor_local.execute(
              "SELECT id FROM clientes WHERE UPPER(nombre) = ? AND activo = 1",
              (nombre_norm,),
          )
          existe_nombre = cursor_local.fetchone()

          existe_ruc = None
          if ruc_norm:
            cursor_local.execute(
                "SELECT nombre FROM clientes WHERE ruc_ci = ? AND activo = 1",
                (ruc_norm,),
            )
            existe_ruc = cursor_local.fetchone()

          if existe_nombre:
            st.warning(f"⚠️ El cliente '{nombre_norm}' ya existe.")
          else:
            if existe_ruc:
              st.info(
                  f"ℹ️ Nota: El RUC {ruc_norm} ya está asociado a"
                  f" '{existe_ruc[0]}'."
              )

            try:
              cursor_local.execute(
                  """
                                INSERT INTO clientes (nombre, apodo, telefono, ruc_ci, activo, sincronizado)
                                VALUES (?, ?, ?, ?, 1, 0)
                            """,
                  (nombre_norm, empresa_norm, telefono.strip(), ruc_norm),
              )
              conn_local.commit()
              ejecutar_sincronizacion_completa()
              st.success(
                  f"✅ ¡Registro exitoso! '{nombre_norm}' guardado"
                  " correctamente."
              )
            except Exception as e:
              st.error(f"❌ Error al guardar: {e}")

  with tab2:
    st.subheader("Base de Datos Actual")
    df_clientes = pd.read_sql_query(
        "SELECT id, nombre, apodo as Empresa, telefono, ruc_ci FROM clientes"
        " WHERE activo = 1 AND nombre != 'ELIMINAR'",
        conn,
    )

    busqueda = st.text_input("🔍 Buscar cliente por nombre o empresa:", "")
    if busqueda:
      df_clientes = df_clientes[
          df_clientes["nombre"].str.contains(busqueda, case=False, na=False)
          | df_clientes["Empresa"].str.contains(busqueda, case=False, na=False)
      ]
    df_clientes = df_clientes.drop_duplicates(subset=["id"]).reset_index(
        drop=True
    )
    st.dataframe(df_clientes, use_container_width=True)

    st.markdown("---")
    st.subheader("📝 Editar Datos de Cliente")

    clientes_edicion = pd.read_sql_query(
        "SELECT id, nombre, apodo, telefono, ruc_ci FROM clientes WHERE activo"
        " = 1 GROUP BY id, nombre",
        conn,
    )

    if not clientes_edicion.empty:
      opciones_cliente = {}
      for _, row in clientes_edicion.iterrows():
        clave = f"{row['id']} - {row['nombre']}"
        opciones_cliente[clave] = {
            "id": row["id"],
            "nombre": row["nombre"],
            "apodo": row["apodo"],
            "telefono": row["telefono"],
            "ruc_ci": row["ruc_ci"],
        }

      seleccion = st.selectbox(
          "Seleccione el cliente para modificar:",
          options=list(opciones_cliente.keys()),
      )
      datos_actuales = opciones_cliente[seleccion]

      val_nom = (
          str(datos_actuales["nombre"])
          if pd.notna(datos_actuales["nombre"])
          else ""
      )
      val_apo = (
          str(datos_actuales["apodo"])
          if pd.notna(datos_actuales["apodo"])
          else ""
      )
      val_tel = (
          str(datos_actuales["telefono"])
          if pd.notna(datos_actuales["telefono"])
          else ""
      )
      val_ruc = (
          str(datos_actuales["ruc_ci"])
          if pd.notna(datos_actuales["ruc_ci"])
          else ""
      )

      with st.form("form_edicion_cliente"):
        col_e1, col_e2 = st.columns(2)
        with col_e1:
          n_nombre = st.text_input("Nombre Completo:", value=val_nom)
          n_empresa = st.text_input("Empresa / Apodo:", value=val_apo)
        with col_e2:
          n_telefono = st.text_input("Teléfono:", value=val_tel)
          n_ruc = st.text_input("RUC / CI:", value=val_ruc)

        if st.form_submit_button("Guardar Cambios"):
          actualizar_datos_cliente(
              datos_actuales["id"], n_nombre, n_empresa, n_telefono, n_ruc
          )
          st.success("¡Datos actualizados!")
          st.rerun()
    else:
      st.info("No hay clientes registrados.")

  with tab3:
    st.subheader("Desactivar Cliente")
    st.warning(
        "Esto ocultará al cliente de las listas de ventas, pero no borrará sus"
        " registros históricos."
    )

    df_bajas = pd.read_sql_query(
        "SELECT id, nombre, apodo FROM clientes WHERE activo = 1", conn
    )

    if not df_bajas.empty:
      opciones_baja = {
          f"{row['id']} - {row['nombre']} ({row['apodo']})": row["id"]
          for _, row in df_bajas.iterrows()
      }
      cliente_a_eliminar = st.selectbox(
          "Seleccione el cliente a desactivar:",
          options=list(opciones_baja.keys()),
      )
      id_para_baja = opciones_baja[cliente_a_eliminar]

      if st.button("Confirmar Baja Definitiva"):
        cambiar_estado_cliente(id_para_baja, activo=False)
        st.error(f"Cliente con ID {id_para_baja} ha sido desactivado.")
        st.rerun()
    else:
      st.info("No hay clientes activos para dar de baja.")

# ==========================================
# 8. VISTA: ÓRDENES DE TRABAJO (OT)
# ==========================================
elif choice == "📝 Órdenes de Trabajo":
  st.title("Generador de Comprobantes (OT)")
  df_ot = pd.read_sql_query(
      """
        SELECT 
            o.id as OT,
            n.nombre as Negocio,
            c.nombre as Cliente,
            COALESCE(NULLIF(c.apodo, ''), c.nombre) as Empresa,
            o.descripcion as Trabajo,
            CAST(o.monto_total AS INTEGER) as TotalReal,
            o.estado as Estado,
            c.telefono as Tel
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
        JOIN negocios n ON o.negocio_id = n.id
        WHERE o.estado != 'Entregado'
        GROUP BY o.id
    """,
      conn,
  )

  if not df_ot.empty:
    st.dataframe(
        df_ot.drop(columns=["Tel"]),
        use_container_width=True,
        hide_index=True,
        key="tabla_ots_activa",
    )
    ot_sel_ver = st.selectbox("Seleccione OT:", df_ot["OT"])
    if st.button("Generar Mensaje de OT"):
      r = df_ot[df_ot["OT"] == ot_sel_ver].iloc[0]
      monto_ot_fmt = f"{int(r['TotalReal']):,}".replace(",", ".")
      txt = (
          f"📄 *OT #{r['OT']} - {r['Empresa']}*\nCliente:"
          f" {r['Cliente']}\nTrabajo: {r['Trabajo']}\nTotal Actualizado:"
          f" {monto_ot_fmt} Gs."
      )
      st.code(txt)
      tel_clean = str(r["Tel"]).replace(" ", "").replace("+", "")
      st.markdown(
          f"[📲 Enviar por WhatsApp](https://wa.me/{tel_clean}?text={urllib.parse.quote(txt)})"
      )
  else:
    st.info("No hay órdenes de trabajo activas.")

  st.markdown("---")
  st.subheader("🛠️ Editar y Gestionar OT")

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
      conn,
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

    df_pagos_ot = pd.read_sql_query(
        f"SELECT id, monto_cuota, estado_pago, notas FROM pagos WHERE orden_id"
        f" = {ot_id}",
        conn,
    )

    entrega_actual_val = 0
    if not df_pagos_ot.empty:
      entrega_actual_val = df_pagos_ot[
          df_pagos_ot["notas"].fillna("") == "ENTREGA INICIAL"
      ]["monto_cuota"].sum()

    monto_tot_def = (
        int(datos_ot["monto_total"])
        if pd.notna(datos_ot["monto_total"])
        else 0
    )
    costo_ins_def = (
        int(datos_ot["costo_insumos"])
        if pd.notna(datos_ot["costo_insumos"])
        else 0
    )
    desc_ot_def = (
        str(datos_ot["descripcion"])
        if pd.notna(datos_ot["descripcion"])
        else ""
    )

    with st.form("form_edicion_completa_ot"):
      col_ot1, col_ot2 = st.columns(2)

      estados_permitidos = [
          "Pendiente",
          "En Proceso",
          "Finalizada",
          "Cancelada",
          "Entregado",
          "Venta",
      ]
      estado_actual = datos_ot["estado"]
      indice_default = (
          estados_permitidos.index(estado_actual)
          if estado_actual in estados_permitidos
          else 0
      )

      with col_ot1:
        nuevo_monto = st.number_input(
            "Monto Total:", value=monto_tot_def, step=50000
        )
        st.info(
            f"Confirmar total: **{int(nuevo_monto):,} Gs.**".replace(",", ".")
        )

        nueva_entrega_ot = st.number_input(
            "Entrega Inicial:", value=int(entrega_actual_val), step=50000
        )
        st.info(
            f"Confirmar entrega: **{int(nueva_entrega_ot):,} Gs.**".replace(
                ",", "."
            )
        )

        nuevo_estado = st.selectbox(
            "Estado del Trabajo:",
            options=estados_permitidos,
            index=indice_default,
        )

      with col_ot2:
        nuevo_costo = st.number_input(
            "Costo de Insumos / Repuestos:", value=costo_ins_def, step=10000
        )
        st.info(f"Costo: **{int(nuevo_costo):,} Gs.**".replace(",", "."))
        nueva_desc = st.text_area(
            "Descripción detallada:",
            value=desc_ot_def,
            key=f"edit_desc_{ot_seleccionada}",
        )

        cuotas_pendientes_count = (
            len(df_pagos_ot[df_pagos_ot["estado_pago"] == "Pendiente"])
            if not df_pagos_ot.empty
            else 1
        )
        cant_cuotas_reajuste = st.number_input(
            "Cantidad de Cuotas Restantes",
            min_value=1,
            value=max(cuotas_pendientes_count, 1),
        )

      boton_guardar = st.form_submit_button(
          "💾 Guardar Cambios y Reajustar Saldos"
      )

    if boton_guardar:
      try:
        id_actualizar = int(datos_ot["id"])
        with sqlite3.connect(DB_PATH) as conn_edit:
          cursor_edit = conn_edit.cursor()

          sql_update = """
                        UPDATE ordenes 
                        SET monto_total = ?, costo_insumos = ?, descripcion = ?, estado = ?, sincronizado = 0 
                        WHERE id = ?
                    """
          cursor_edit.execute(
              sql_update,
              (
                  int(nuevo_monto),
                  int(nuevo_costo),
                  nueva_desc.upper(),
                  nuevo_estado,
                  id_actualizar,
              ),
          )

          cursor_edit.execute(
              "DELETE FROM pagos WHERE orden_id = ?", (id_actualizar,)
          )

          if nueva_entrega_ot > 0:
            cursor_edit.execute(
                """
                            INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
                            VALUES (?, ?, ?, 'Pagado', 'ENTREGA INICIAL', 0)
                        """,
                (
                    id_actualizar,
                    nueva_entrega_ot,
                    datetime.now().strftime("%Y-%m-%d"),
                ),
            )

          saldo_restante_ot = nuevo_monto - nueva_entrega_ot
          if saldo_restante_ot > 0:
            if int(cant_cuotas_reajuste) == 1:
              cursor_edit.execute(
                  """
                                INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
                                VALUES (?, ?, ?, 'Pendiente', 'SALDO CONTADO', 0)
                            """,
                  (
                      id_actualizar,
                      saldo_restante_ot,
                      datetime.now().strftime("%Y-%m-%d"),
                  ),
              )
            else:
              monto_por_cuota_ot = saldo_restante_ot / cant_cuotas_reajuste
              for i in range(1, int(cant_cuotas_reajuste) + 1):
                vence_reajuste = datetime.now() + relativedelta(months=i)
                cursor_edit.execute(
                    """
                                    INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
                                    VALUES (?, ?, ?, 'Pendiente', ?, 0)
                                """,
                    (
                        id_actualizar,
                        monto_por_cuota_ot,
                        vence_reajuste.strftime("%Y-%m-%d"),
                        f"CUOTA {i}/{cant_cuotas_reajuste}",
                    ),
                )

          conn_edit.commit()
          ejecutar_sincronizacion_completa()

        st.success(
            f"✅ ¡OT {id_actualizar} reajustada y actualizada correctamente!"
        )
        time.sleep(1)
        st.rerun()

      except Exception as e:
        st.error(f"❌ Error al guardar: {e}")

    ot_sel_borrar = datos_ot["id"]
    st.markdown("---")
    confirmacion = st.popover("🗑️ Eliminar esta OT")

    with confirmacion:
      st.warning(
          "⚠️ ¿Estás seguro? Esta acción moverá la OT"
          f" {ot_sel_borrar} a la papelera."
      )
      if st.button("Sí, borrar ahora"):
        try:
          with sqlite3.connect(DB_PATH) as conn_del:
            cursor_del = conn_del.cursor()
            cursor_del.execute(
                """
                            INSERT INTO historial_eliminacion (orden_id, cliente, monto, detalle)
                            SELECT o.id, c.nombre, o.monto_total, o.descripcion
                            FROM ordenes o 
                            JOIN clientes c ON o.cliente_id = c.id
                            WHERE o.id = ?
                        """,
                (ot_sel_borrar,),
            )

            cursor_del.execute(
                "DELETE FROM ordenes WHERE id = ?", (ot_sel_borrar,)
            )
            cursor_del.execute(
                "DELETE FROM pagos WHERE orden_id = ?", (ot_sel_borrar,)
            )
            conn_del.commit()
            ejecutar_sincronizacion_completa()

          st.success(f"✅ OT {ot_sel_borrar} enviada a la papelera.")
          time.sleep(1)
          st.rerun()
        except Exception as e:
          st.error(f"❌ Error técnico: {e}")

  st.markdown("### ♻️ Recuperación")
  with st.expander("Ver Papelera de Reciclaje"):
    df_borrados = pd.read_sql_query(
        "SELECT * FROM historial_eliminacion ORDER BY fecha_eliminacion DESC",
        sqlite3.connect(DB_PATH),
    )

    if not df_borrados.empty:
      st.dataframe(df_borrados)
      ultima = df_borrados.iloc[0]

      if st.button(f"↩️ Deshacer: Recuperar OT {int(ultima['orden_id'])}"):
        try:
          with sqlite3.connect(DB_PATH) as conn_undo:
            conn_undo.execute(
                """
                            INSERT INTO ordenes (id, monto_total, descripcion, estado, cliente_id, negocio_id, sincronizado)
                            VALUES (?, ?, ?, 'Pendiente', 
                                (SELECT id FROM clientes WHERE apodo = ? OR nombre = ? LIMIT 1), 
                                (SELECT id FROM negocios LIMIT 1), 0)
                        """,
                (
                    int(ultima["orden_id"]),
                    ultima["monto"],
                    ultima["detalle"],
                    ultima["cliente"],
                    ultima["cliente"],
                ),
            )

            conn_undo.execute(
                "DELETE FROM historial_eliminacion WHERE id = ?",
                (int(ultima["id"]),),
            )
            conn_undo.commit()
            ejecutar_sincronizacion_completa()

          st.success("Orden recuperada correctamente.")
          st.rerun()
        except Exception as e:
          st.error(f"Error al recuperar: {e}")
    else:
      st.info("La papelera está vacía.")

  st.markdown("---")
  with st.popover("🚨 Limpieza Definitiva"):
    st.warning(
        "¿Estás seguro de que querés vaciar la papelera? Esta acción no se"
        " puede deshacer."
    )
    if st.button("Confirmar: Vaciar todo"):
      try:
        with sqlite3.connect(DB_PATH) as conn_clear:
          conn_clear.execute("DELETE FROM historial_eliminacion")
          conn_clear.commit()
          ejecutar_sincronizacion_completa()
        st.success("Papelera vaciada con éxito.")
        st.rerun()
      except Exception as e:
        st.error(f"Error al vaciar: {e}")

# ==========================================
# 9. VISTA: PRESUPUESTOS EXPRESS (MÓDULO)
# ==========================================
elif choice == "📄 Presupuestos Express":
  ejecutar_render_modulo(presupuestos, "presupuestos")

# ==========================================
# 10. VISTA: RECORDATORIOS (MÓDULO)
# ==========================================
elif choice == "🔔 Recordatorios":
  ejecutar_render_modulo(recordatorios, "Recordatorios")

# ==========================================
# 11. VISTA: HISTORIAL DE COBRADOS
# ==========================================
elif choice == "✅ Historial de Cobrados":
  st.title("Registro Histórico de Ingresos")

  df_h = pd.read_sql_query(
      """
        SELECT p.id as ID, 
               p.fecha_vencimiento as Fecha, 
               n.nombre as Negocio, 
               c.nombre as Cliente, 
               COALESCE(NULLIF(c.apodo, ''), c.nombre) as Empresa, 
               p.monto_cuota as Cobrado
        FROM pagos p 
        JOIN ordenes o ON p.orden_id = o.id 
        JOIN clientes c ON o.cliente_id = c.id
        JOIN negocios n ON o.negocio_id = n.id 
        WHERE p.estado_pago = 'Pagado' 
        ORDER BY Fecha DESC
    """,
      conn,
  )

  if not df_h.empty:
    df_display = df_h.copy()
    df_display["Cobrado"] = df_display["Cobrado"].apply(
        lambda x: f"{int(x):,} Gs.".replace(",", ".")
    )
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("↩️ Deshacer Cobro Realizado por Error")

    c_rev1, c_rev2 = st.columns([2, 1])
    with c_rev1:
      id_pago_sel = st.selectbox(
          "Seleccioná el ID del pago a devolver a 'Pendiente':",
          options=df_h["ID"],
      )
      r_sel = df_h[df_h["ID"] == id_pago_sel].iloc[0]
      monto_fmt = f"{int(r_sel['Cobrado']):,}".replace(",", ".")
      st.info(
          f"Seleccionado: **ID #{r_sel['ID']}** - {r_sel['Cliente']}"
          f" ({r_sel['Empresa']}) | Monto: **{monto_fmt} Gs.**"
      )

    with c_rev2:
      st.write("")
      st.write("")
      if st.button("🔄 Volver a Pendiente"):
        with sqlite3.connect(DB_PATH) as conn_rev:
          conn_rev.execute(
              "UPDATE pagos SET estado_pago = 'Pendiente', sincronizado = 0 WHERE id = ?",
              (int(id_pago_sel),),
          )
          conn_rev.commit()
          ejecutar_sincronizacion_completa()
        st.success(
            f"✅ El pago ID #{id_pago_sel} volvió a Cobros Pendientes."
        )
        time.sleep(1)
        st.rerun()
  else:
    st.info(
        "El historial está vacío. Los pagos aparecerán aquí una vez que los"
        " confirmes en 'Cobros Pendientes'."
    )

# ==========================================
# 12. VISTA: NUEVA VENTA / SERVICIO
# ==========================================
elif choice == "🛒 Nueva Venta / Servicio":
  st.title("Cargar Nueva Operación")

  negocio_nom = st.radio(
      "Facturar con:", ["GHV - Service", "OnXpert Software"], horizontal=True
  )
  n_id = 1 if negocio_nom == "GHV - Service" else 2

  df_c = pd.read_sql_query(
      "SELECT id, apodo || ' - ' || nombre as cliente_display FROM clientes"
      " WHERE activo = 1",
      conn,
  )

  if not df_c.empty:
    cliente_dict = dict(zip(df_c["cliente_display"], df_c["id"]))
    c_sel = st.selectbox(
        "Seleccionar Cliente:", options=list(cliente_dict.keys())
    )

    tipo_op = st.selectbox("¿Qué vas a registrar?", [
        "🛒 Venta de Artículo (Hardware)",
        "🛠️ Servicio Técnico (GHV)",
        "💻 Software / Membresía (OnXpert)",
    ])

    if tipo_op == "🛒 Venta de Artículo (Hardware)":
      tipo_v = st.radio("Condición", ["Contado", "Cuotas"], horizontal=True)
      cant_c = (
          st.number_input(
              "Cantidad de Cuotas", min_value=2, max_value=36, value=2
          )
          if tipo_v == "Cuotas"
          else 1
      )

      st.markdown("---")
      modo_inv_v = st.checkbox(
          "🔍 Seleccionar producto desde Inventario registrado", value=False
      )

      prod_inv_id = None
      precio_sug_v = 0
      costo_sug_v = 0
      desc_sug_v = ""

      if modo_inv_v:
        df_prod_v = pd.read_sql_query(
            """
                    SELECT id, categoria || ' ' || marca || ' (' || capacidad_especificacion || ') - Stock: ' || stock as display, 
                           precio_venta, precio_costo, stock, categoria || ' ' || marca || ' (' || capacidad_especificacion || ')' as nombre_corto
                    FROM productos WHERE stock > 0
                """,
            conn,
        )

        if not df_prod_v.empty:
          p_v_sel_display = st.selectbox(
              "Buscar Producto en Stock:", df_prod_v["display"]
          )
          match_v = df_prod_v[
              df_prod_v["display"] == p_v_sel_display
          ].iloc[0]
          precio_sug_v = int(match_v["precio_venta"])
          costo_sug_v = int(match_v["precio_costo"])
          desc_sug_v = str(match_v["nombre_corto"])
          prod_inv_id = int(match_v["id"])
        else:
          st.info(
              "No hay productos disponibles en el Inventario con Stock mayor"
              " a 0."
          )

      c1, c2 = st.columns(2)
      with c1:
        monto_v = st.number_input(
            "Precio Venta (Gs)",
            min_value=0,
            step=50000,
            value=precio_sug_v,
            format="%d",
        )
        entrega = st.number_input(
            "Entrega Inicial (Gs)", min_value=0, step=50000, format="%d"
        )
        if entrega > 0:
          st.info(f"Entrega: **{int(entrega):,} Gs.**".replace(",", "."))

      with c2:
        costo_h = st.number_input(
            "Costo Compra (Gs)",
            min_value=0,
            step=50000,
            value=costo_sug_v,
            format="%d",
        )
        f_v = st.date_input("Fecha", value=datetime.now().date())

      ganancia_v = monto_v - costo_h
      margen_v = (ganancia_v / monto_v * 100) if monto_v > 0 else 0.0

      mc1, mc2, mc3 = st.columns(3)
      mc1.info(f"**Monto:** {int(monto_v):,} Gs.".replace(",", "."))
      mc2.warning(f"**Costo:** {int(costo_h):,} Gs.".replace(",", "."))
      if ganancia_v >= 0:
        mc3.success(
            f"**Ganancia:** {int(ganancia_v):,} Gs. ({margen_v:.1f}%)".replace(
                ",", "."
            )
        )
      else:
        mc3.error(
            f"**Pérdida:** {int(ganancia_v):,} Gs. ({margen_v:.1f}%)".replace(
                ",", "."
            )
        )

      descontar_stock_v = False
      if modo_inv_v and prod_inv_id:
        descontar_stock_v = st.checkbox(
            "📦 Descontar 1 unidad del Stock en Inventario", value=True
        )

      with st.form("form_hardware_detalles", clear_on_submit=True):
        prod = st.text_input("Producto / Descripción", value=desc_sug_v)
        enviar = st.form_submit_button("Confirmar Venta")

      if enviar:
        if not prod:
          st.error("⚠️ Por favor ingresa una descripción para el producto.")
        else:
          try:
            with sqlite3.connect(DB_PATH) as conn_op:
              cursor_op = conn_op.cursor()
              cursor_op.execute(
                  """
                                INSERT INTO ordenes (negocio_id, cliente_id, descripcion, monto_total, costo_insumos, fecha_ingreso, estado, sincronizado)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                            """,
                  (
                      n_id,
                      cliente_dict[c_sel],
                      prod.upper(),
                      monto_v,
                      costo_h,
                      f_v.strftime("%Y-%m-%d"),
                      "Venta",
                  ),
              )

              orden_id = cursor_op.lastrowid

              if modo_inv_v and prod_inv_id and descontar_stock_v:
                cursor_op.execute(
                    "UPDATE productos SET stock = stock - 1, sincronizado = 0 WHERE id = ?",
                    (prod_inv_id,),
                )

              if entrega > 0:
                cursor_op.execute(
                    """
                                    INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
                                    VALUES (?, ?, ?, 'Pagado', 'ENTREGA INICIAL', 0)
                                """,
                    (orden_id, entrega, f_v.strftime("%Y-%m-%d")),
                )

              saldo = monto_v - entrega
              if saldo > 0:
                if tipo_v == "Contado":
                  cursor_op.execute(
                      """
                                        INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
                                        VALUES (?, ?, ?, 'Pendiente', 'SALDO CONTADO', 0)
                                    """,
                      (orden_id, saldo, f_v.strftime("%Y-%m-%d")),
                  )
                else:
                  n_cuotas = cant_c
                  por_cuota = saldo / n_cuotas
                  for i in range(1, n_cuotas + 1):
                    vence_c = f_v + relativedelta(months=i)
                    cursor_op.execute(
                        """
                                            INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
                                            VALUES (?, ?, ?, 'Pendiente', ?, 0)
                                        """,
                        (
                            orden_id,
                            por_cuota,
                            vence_c.strftime("%Y-%m-%d"),
                            f"CUOTA {i}/{n_cuotas}",
                        ),
                    )

              conn_op.commit()
              ejecutar_sincronizacion_completa()
              st.success("✅ ¡Venta registrada exitosamente!")
              time.sleep(1)
              st.rerun()
          except Exception as e:
            st.error(f"Error al guardar: {e}")

    elif tipo_op == "🛠️ Servicio Técnico (GHV)":
      eq = st.text_input("Equipo (Ej: Notebook ASUS X515)", key="svc_eq")
      fa = st.text_input(
          "Falla reportada (Ej: Lentitud extrema / Mantenimiento)", key="svc_fa"
      )

      c1, c2 = st.columns(2)
      with c1:
        monto_cliente_mo = st.number_input(
            "Precio Trabajo / Mano de Obra al Cliente (Gs)",
            min_value=0,
            step=10000,
            value=0,
            key="svc_mo",
        )
        costo_tercerizado = st.number_input(
            "Costo Tercerizado - Lo que pagás afuera (Gs)",
            min_value=0,
            step=10000,
            value=0,
            key="svc_terc",
        )

        mano_de_obra_pura = max(0, monto_cliente_mo - costo_tercerizado)
        st.caption(
            f"💡 **Ganancia Pura GHV (Calculada):**"
            f" {int(mano_de_obra_pura):,} Gs.".replace(",", ".")
        )

      with c2:
        entrega_svc = st.number_input(
            "Entrega Inicial del Cliente (Gs)",
            min_value=0,
            step=50000,
            key="svc_ent",
        )
        cant_c = st.number_input(
            "Cuotas del Saldo Restante", min_value=1, value=1, key="svc_cuotas"
        )
        f_v = st.date_input(
            "Fecha Temprana", value=datetime.now().date(), key="svc_fecha"
        )

      st.markdown("---")
      st.markdown("#### ➕ Agregar Insumos / Repuestos desde Stock")

      df_prod_disponibles = pd.read_sql_query(
          """
                SELECT id, categoria || ' ' || marca || ' (' || capacidad_especificacion || ') - Stock: ' || stock as display, 
                       precio_venta, precio_costo, stock, categoria || ' ' || marca || ' (' || capacidad_especificacion || ')' as nombre_corto
                FROM productos WHERE stock > 0
            """,
          conn,
      )

      if "insumos_orden" not in st.session_state:
        st.session_state.insumos_orden = []

      if df_prod_disponibles.empty:
        st.info(
            "No hay productos cargados en el Inventario o no queda stock"
            " disponible."
        )
      else:
        col_sel_p, col_cant_p, col_btn_p = st.columns([3, 1, 1])
        p_elegido_display = col_sel_p.selectbox(
            "Seleccionar Repuesto:",
            df_prod_disponibles["display"],
            key="p_insumo_sel",
        )
        cant_elegida = col_cant_p.number_input(
            "Cantidad", min_value=1, value=1, key="p_insumo_cant"
        )

        if col_btn_p.button("➕ Añadir Insumo", use_container_width=True):
          match_p = df_prod_disponibles[
              df_prod_disponibles["display"] == p_elegido_display
          ].iloc[0]
          if cant_elegida > match_p["stock"]:
            st.error(
                f"No podés agregar {cant_elegida} unidades. Solo quedan"
                f" {match_p['stock']} en stock."
            )
          else:
            st.session_state.insumos_orden.append({
                "id": int(match_p["id"]),
                "nombre": match_p["nombre_corto"],
                "cantidad": int(cant_elegida),
                "precio_venta": float(match_p["precio_venta"]),
                "precio_costo": float(match_p["precio_costo"]),
            })
            st.toast("Insumo agregado a la lista temporal.")

      total_insumos_venta = 0.0
      total_insumos_costo = 0.0
      detalle_insumos_texto = ""

      if st.session_state.insumos_orden:
        st.markdown("##### 📋 Lista de Insumos para esta OT")
        for idx, ins in enumerate(st.session_state.insumos_orden):
          subtotal_i = ins["cantidad"] * ins["precio_venta"]
          total_insumos_venta += subtotal_i
          total_insumos_costo += ins["cantidad"] * ins["precio_costo"]
          detalle_insumos_texto += f"\n- {ins['cantidad']}x {ins['nombre']}"

          c_i1, c_i2, c_i3 = st.columns([3, 1, 1])
          c_i1.markdown(f"🔹 **{ins['nombre']}** (Cant: {ins['cantidad']})")
          c_i2.markdown(f"{int(subtotal_i):,} Gs.".replace(",", "."))
          if c_i3.button("🗑️", key=f"del_ins_{idx}"):
            st.session_state.insumos_orden.pop(idx)
            st.rerun()

      precio_final_calculado = monto_cliente_mo + total_insumos_venta
      total_costos_calculado = total_insumos_costo + costo_tercerizado
      ganancia_estimada = precio_final_calculado - total_costos_calculado

      st.markdown("---")
      st.markdown(
          "### 🧮 Total Proyectado al Cliente:"
          f" **{int(precio_final_calculado):,} Gs.**".replace(",", ".")
      )
      st.caption(
          f"Trabajo/Servicio: {int(monto_cliente_mo):,} Gs.".replace(",", ".")
          + " | Repuestos:"
          f" {int(total_insumos_venta):,} Gs.".replace(",", ".")
      )
      st.info(
          f"💡 **Costo Real Total:** {int(total_costos_calculado):,}"
          " Gs. | **Ganancia Neta Estimada:**"
          f" {int(ganancia_estimada):,} Gs.".replace(",", ".")
      )

      col_sub1, col_sub2 = st.columns(2)
      with col_sub1:
        enviar_svc = st.button(
            "🚀 Registrar Servicio Técnico Completo", use_container_width=True
        )
      with col_sub2:
        if st.button("❌ Limpiar Todo", use_container_width=True):
          st.session_state.insumos_orden = []
          st.rerun()

      if enviar_svc:
        if not eq or not fa:
          st.error("⚠️ Por favor, completa el equipo y la falla.")
        else:
          try:
            with sqlite3.connect(DB_PATH) as conn_op:
              cursor_op = conn_op.cursor()
              id_cliente_actual = cliente_dict[c_sel]

              descripcion_completa_ot = f"{eq.upper()} - FALLA: {fa.upper()}"
              if costo_tercerizado > 0:
                descripcion_completa_ot += (
                    "\n\n⚙️ TRABAJO TERCERIZADO INCLUIDO (Costo:"
                    f" {int(costo_tercerizado):,} Gs.)".replace(",", ".")
                )
              if detalle_insumos_texto:
                descripcion_completa_ot += (
                    f"\n\n🛠️ COMPONENTES INSTALADOS:{detalle_insumos_texto.upper()}"
                )

              cursor_op.execute(
                  """
                                INSERT INTO ordenes (negocio_id, cliente_id, descripcion, fecha_ingreso, monto_total, costo_insumos, estado, sincronizado)
                                VALUES (1, ?, ?, ?, ?, ?, 'En Proceso', 0)
                            """,
                  (
                      id_cliente_actual,
                      descripcion_completa_ot,
                      f_v.strftime("%Y-%m-%d"),
                      precio_final_calculado,
                      total_costos_calculado,
                  ),
              )

              orden_id = cursor_op.lastrowid

              for ins in st.session_state.insumos_orden:
                cursor_op.execute(
                    """
                                    UPDATE productos 
                                    SET stock = stock - ?, sincronizado = 0 
                                    WHERE id = ?
                                """,
                    (ins["cantidad"], ins["id"]),
                )

              if entrega_svc > 0:
                cursor_op.execute(
                    """
                                    INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
                                    VALUES (?, ?, ?, 'Pagado', 'ENTREGA INICIAL', 0)
                                """,
                    (orden_id, entrega_svc, f_v.strftime("%Y-%m-%d")),
                )

              saldo_restante = precio_final_calculado - entrega_svc
              if saldo_restante > 0:
                if int(cant_c) == 1:
                  cursor_op.execute(
                      """
                                        INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
                                        VALUES (?, ?, ?, 'Pendiente', 'SALDO CONTADO', 0)
                                    """,
                      (orden_id, saldo_restante, f_v.strftime("%Y-%m-%d")),
                  )
                else:
                  monto_c = saldo_restante / int(cant_c)
                  for i in range(1, int(cant_c) + 1):
                    vencimiento = f_v + relativedelta(months=i)
                    cursor_op.execute(
                        """
                                            INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas, sincronizado)
                                            VALUES (?, ?, ?, 'Pendiente', ?, 0)
                                        """,
                        (
                            orden_id,
                            monto_c,
                            vencimiento.strftime("%Y-%m-%d"),
                            f"CUOTA {i}/{int(cant_c)}",
                        ),
                    )

              conn_op.commit()
              ejecutar_sincronizacion_completa()

              st.session_state.insumos_orden = []
              st.success(
                  "✅ ¡Servicio Técnico Registrado con éxito! OT"
                  f" #{orden_id} generada y Stock actualizado."
              )
              time.sleep(1)
              st.rerun()

          except Exception as e:
            st.error(f"❌ Error al registrar: {e}")

    elif tipo_op == "💻 Software / Membresía (OnXpert)":
      soft = st.text_input(
          "Nombre / Descripción del Sistema",
          placeholder="Ej: Sistema de Automatización y Marcación",
      )

      c1, c2 = st.columns(2)
      with c1:
        ms = st.number_input(
            "Costo Software / Implementación (Gs)",
            min_value=0,
            step=100000,
            value=0,
            format="%d",
        )
        cuotas_soft = st.number_input(
            "Pagos para el Software (1 = Pago único)",
            min_value=1,
            max_value=12,
            value=1,
        )
        if ms > 0:
          val_c_soft = ms / cuotas_soft
          st.caption(
              f"💡 Software: {cuotas_soft} pago(s) de"
              f" **{int(val_c_soft):,} Gs.**".replace(",", ".")
          )

      with c2:
        mm = st.number_input(
            "Membresía Mensual / Mantenimiento (Gs)",
            min_value=0,
            step=50000,
            value=0,
            format="%d",
        )
        meses_memb = st.number_input(
            "Cantidad de meses de Membresía",
            min_value=1,
            max_value=36,
            value=12,
        )
        if mm > 0:
          st.caption(
              f"💡 Membresía: {meses_memb} mes(es) de"
              f" **{int(mm):,} Gs.**".replace(",", ".")
          )

      f_v = st.date_input(
          "Fecha de Inicio / Contrato", value=datetime.now().date()
      )

      monto_total_contrato = ms + (mm * meses_memb)
      st.info(
          "💰 **Monto Total del Contrato:**"
          f" {int(monto_total_contrato):,} Gs.".replace(",", ".")
      )

      if st.button(
          "🚀 Registrar Software y Membresía", use_container_width=True
      ):
        if not soft:
          st.error("⚠️ Por favor ingresa el nombre o descripción del sistema.")
        else:
          partes = c_sel.split(" - ")
          empresa_p = partes[0] if len(partes) > 0 else ""
          nombre_p = partes[1] if len(partes) > 1 else c_sel

          registrar_venta_onxpert(
              cliente=nombre_p,
              empresa=empresa_p,
              telefono="",
              desc=soft.upper(),
              monto_soft=ms,
              cuotas_soft=int(cuotas_soft),
              monto_memb=mm,
              cuotas_memb=int(meses_memb),
              fecha_manual=f_v,
          )
          st.success(
              "✅ Operación de Software/Membresía registrada correctamente."
          )
          time.sleep(1)
          st.rerun()
  else:
    st.warning("Primero debés dar de alta un cliente en 'Gestión de Clientes'.")

# ==========================================
# 13. VISTA: REPORTES AVANZADOS
# ==========================================
elif choice == "📈 Reportes Avanzados":
  st.header("📊 Reportes y Análisis de Negocio")
  tab_r1, tab_r2 = st.tabs(
      ["Rentabilidad por Negocio", "Comportamiento de Cliente"]
  )

  with tab_r1:
    st.subheader("Análisis de Margen Real")

    df_rent = pd.read_sql_query(
        """
            SELECT 
                n.nombre as Negocio,
                COALESCE((
                    SELECT SUM(p.monto_cuota) 
                    FROM pagos p 
                    JOIN ordenes o2 ON p.orden_id = o2.id 
                    WHERE o2.negocio_id = n.id
                ), 0) as Ingresos_Totales,
                COALESCE((
                    SELECT SUM(o3.costo_insumos) 
                    FROM ordenes o3 
                    WHERE o3.negocio_id = n.id
                ), 0) as Costos_Totales
            FROM negocios n
        """,
        conn,
    )

    df_rent["Utilidad_Neta"] = (
        df_rent["Ingresos_Totales"] - df_rent["Costos_Totales"]
    )
    col_graf, col_tabla = st.columns([1, 1])

    with col_graf:
      if df_rent["Utilidad_Neta"].sum() > 0:
        fig_rent = px.pie(
            df_rent,
            values="Utilidad_Neta",
            names="Negocio",
            title="Distribución de Utilidad Neta",
            hole=0.4,
            color_discrete_sequence=["#3498db", "#e67e22"],
        )
        st.plotly_chart(fig_rent, use_container_width=True)
      else:
        st.warning("La utilidad total es 0 o negativa para graficar.")

    with col_tabla:
      df_visual = df_rent.copy()

      def pts(x):
        return f"{int(x):,}".replace(",", ".")

      df_visual["Ingresos_Totales"] = df_visual["Ingresos_Totales"].apply(pts)
      df_visual["Costos_Totales"] = df_visual["Costos_Totales"].apply(pts)
      df_visual["Utilidad_Neta"] = df_visual["Utilidad_Neta"].apply(pts)
      st.table(df_visual)

  with tab_r2:
    st.subheader("Análisis de Comportamiento por Cliente")

    df_comp = pd.read_sql_query(
        """
            SELECT 
                c.apodo as Empresa,
                COUNT(DISTINCT o.id) as Cantidad_OTs,
                SUM(o.monto_total) as Volumen_Contratado,
                COALESCE((
                    SELECT SUM(p.monto_cuota) 
                    FROM pagos p 
                    JOIN ordenes o2 ON p.orden_id = o2.id 
                    WHERE o2.cliente_id = c.id AND p.estado_pago = 'Pagado'
                ), 0) as Total_Pagado,
                COALESCE((
                    SELECT SUM(p.monto_cuota) 
                    FROM pagos p 
                    JOIN ordenes o2 ON p.orden_id = o2.id 
                    WHERE o2.cliente_id = c.id AND p.estado_pago = 'Pendiente'
                ), 0) as Saldo_Pendiente
            FROM clientes c
            JOIN ordenes o ON c.id = o.cliente_id
            GROUP BY c.apodo
            ORDER BY Volumen_Contratado DESC
        """,
        conn,
    )

    if not df_comp.empty:
      fig_bar = px.bar(
          df_comp,
          x="Empresa",
          y=["Total_Pagado", "Saldo_Pendiente"],
          title="Saldos Reales por Cliente",
          barmode="stack",
          color_discrete_map={
              "Total_Pagado": "#2ecc71",
              "Saldo_Pendiente": "#e74c3c",
          },
      )
      st.plotly_chart(fig_bar, use_container_width=True)

      df_comp_fmt = df_comp.copy()
      for col in ["Volumen_Contratado", "Total_Pagado", "Saldo_Pendiente"]:
        df_comp_fmt[col] = df_comp_fmt[col].apply(
            lambda x: f"{int(x):,}".replace(",", ".")
        )
      st.dataframe(df_comp_fmt, use_container_width=True)

# ==========================================
# 14. VISTA: INVENTARIO / STOCK
# ==========================================
elif choice == "📦 Inventario / Stock":
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
          with sqlite3.connect(DB_PATH) as conn_inv:
            conn_inv.execute(
                """
                            INSERT INTO productos (categoria, marca, capacidad_especificacion, stock, precio_costo, precio_venta, sincronizado)
                            VALUES (?, ?, ?, ?, ?, ?, 0)
                        """,
                (cat, mrc, cap, cant_stock, p_costo, p_venta),
            )
            conn_inv.commit()
            ejecutar_sincronizacion_completa()
          st.success(
              f"✅ ¡{cat} {mrc} ({cap}) cargado correctamente al stock!"
          )
          time.sleep(1)
          st.rerun()
        except Exception as e:
          st.error(f"❌ Error al guardar producto: {e}")

  with tab_inv2:
    st.subheader("Inventario de Artículos Disponibles")
    df_stock = pd.read_sql_query(
        """
            SELECT id as ID, categoria as Categoría, marca as Marca, 
                   capacidad_especificacion as Detalle, stock as [Stock Disponible], 
                   precio_costo as [Precio_Costo], precio_venta as [Precio_Venta] 
            FROM productos ORDER BY categoria ASC, marca ASC
        """,
        conn,
    )

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
      st.dataframe(df_stock_fmt, use_container_width=True, hide_index=True)

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
            with sqlite3.connect(DB_PATH) as conn_prod_up:
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
              ejecutar_sincronizacion_completa()
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
          with sqlite3.connect(DB_PATH) as conn_prod_del:
            conn_prod_del.execute(
                "DELETE FROM productos WHERE id = ?", (id_prod_editar,)
            )
            conn_prod_del.commit()
            ejecutar_sincronizacion_completa()
          st.error("Producto eliminado del inventario.")
          time.sleep(1)
          st.rerun()
    else:
      st.info("El inventario está vacío actualmente.")

# ==========================================
# 15. VISTA: CONFIGURACIÓN / MI NEGOCIO (MÓDULO)
# ==========================================
elif choice == "⚙️ Configuración / Mi Negocio":
  ejecutar_render_modulo(mi_negocio, "Mi Negocio / Configuración")

# --- HERRAMIENTA TEMPORAL PARA BORRAR IDS ---
with st.sidebar.expander("🛠️ Borrar registros erróneos (pagos)"):
  ids_a_borrar = st.text_input("IDs a eliminar:", value="112, 113, 114")
  if st.button("🗑️ Ejecutar Eliminación en Pagos"):
    try:
      ids_list = [int(x.strip()) for x in ids_a_borrar.split(",") if x.strip()]
      if ids_list:
        with sqlite3.connect("database/sistema.db") as conn:
          placeholders = ",".join(["?"] * len(ids_list))
          conn.execute(
              f"DELETE FROM pagos WHERE id IN ({placeholders})", ids_list
          )
          conn.commit()
        st.success(f"¡Registros {ids_list} eliminados con éxito!")
        st.rerun()
    except Exception as e:
      st.error(f"Error: {e}")

with st.sidebar.expander("🛠️ Ver tablas de la BD"):
  if st.button("🔍 Mostrar tablas"):
    try:
      with sqlite3.connect("database/sistema.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        )
        tablas = cursor.fetchall()
      st.success(f"Tablas encontradas: {tablas}")
    except Exception as e:
      st.error(f"Error: {e}")

with st.sidebar.expander("🛠️ Reparar Nota ID 91"):
  if st.button("📝 Restaurar nota original"):
    try:
      with sqlite3.connect("database/sistema.db") as conn:
        conn.execute(
            "UPDATE pagos SET notas = ? WHERE id = 91",
            ("SOFTWARE / IMPLEMENTACIÓN",),
        )
        conn.commit()
      st.success("¡Nota restaurada con éxito!")
      st.rerun()
    except Exception as e:
      st.error(f"Error: {e}")            