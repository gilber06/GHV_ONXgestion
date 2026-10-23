import os
import sqlite3
import warnings
import streamlit as st
import pandas as pd

warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

st.set_page_config(
    page_title="GHV - Service & OnXpert", layout="wide", page_icon="📈"
)

DB_PATH = os.path.join(BASE_DIR, "database", "sistema.db")

def get_connection():
    if not os.path.exists(os.path.join(BASE_DIR, "database")):
        os.makedirs(os.path.join(BASE_DIR, "database"))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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

def asegurar_columna(cursor, tabla, columna, tipo):
    cursor.execute(f"PRAGMA table_info({tabla})")
    columnas_existentes = [info[1] for info in cursor.fetchall()]
    if columna not in columnas_existentes:
        try:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
        except Exception:
            pass

def inicializar_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS clientes 
                        (id INTEGER PRIMARY KEY, nombre TEXT, apodo TEXT, telefono TEXT, es_companero BOOLEAN)""")
        asegurar_columna(cursor, "clientes", "ruc_ci", "TEXT")
        asegurar_columna(cursor, "clientes", "activo", "INTEGER DEFAULT 1")
        asegurar_columna(cursor, "clientes", "sincronizado", "INTEGER DEFAULT 0")
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS negocios 
                        (id INTEGER PRIMARY KEY, nombre TEXT, sincronizado INTEGER DEFAULT 0)""")
        asegurar_columna(cursor, "negocios", "sincronizado", "INTEGER DEFAULT 0")
            
        cursor.execute("""CREATE TABLE IF NOT EXISTS ordenes 
                        (id INTEGER PRIMARY KEY, negocio_id INTEGER, cliente_id INTEGER, 
                         descripcion TEXT, fecha_ingreso TEXT, monto_total REAL, 
                         costo_insumos REAL DEFAULT 0, estado TEXT,
                         FOREIGN KEY(negocio_id) REFERENCES negocios(id))""")
        asegurar_columna(cursor, "ordenes", "costo_insumos", "REAL DEFAULT 0")
        asegurar_columna(cursor, "ordenes", "estado", "TEXT")
        asegurar_columna(cursor, "ordenes", "sincronizado", "INTEGER DEFAULT 0")  # <-- Columna añadida aquí
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS pagos 
                        (id INTEGER PRIMARY KEY, orden_id INTEGER, monto_cuota REAL, 
                         fecha_vencimiento TEXT, estado TEXT, notas TEXT, sincronizado INTEGER DEFAULT 0)""")
        asegurar_columna(cursor, "pagos", "notas", "TEXT")
        asegurar_columna(cursor, "pagos", "estado", "TEXT")
        asegurar_columna(cursor, "pagos", "sincronizado", "INTEGER DEFAULT 0")

        cursor.execute("UPDATE pagos SET estado = 'Pendiente' WHERE estado IS NULL OR TRIM(estado) = ''")

        cursor.execute("SELECT COUNT(*) FROM negocios")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                "INSERT OR IGNORE INTO negocios (id, nombre, sincronizado) VALUES (?,?,?)",
                [(1, "GHV Service", 0), (2, "OnXpert Software", 0)],
            )

        cursor.execute("""CREATE TABLE IF NOT EXISTS ventas_articulos 
                        (id INTEGER PRIMARY KEY, cliente_id INTEGER, producto TEXT, 
                         tipo_pago TEXT, monto_total REAL, costo_adquisicion REAL, 
                         fecha_venta TEXT)""")

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

inicializar_db()

def _fetch_dashboard_data():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM ordenes")
        res_act = cursor.fetchone()[0]
        cant_activas = res_act if res_act is not None else 0
        if cant_activas == 0:
            cursor.execute("SELECT COUNT(*) FROM ordenes_trabajo")
            cant_activas = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(monto_cuota) FROM pagos WHERE LOWER(TRIM(estado)) = 'pendiente'")
        res_pend = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(monto_cuota) FROM pagos WHERE LOWER(TRIM(estado)) = 'pagado'")
        res_coba = cursor.fetchone()[0] or 0

        if res_pend == 0 and res_coba == 0:
            cursor.execute("SELECT SUM(monto_total) FROM ordenes")
            total_tabla_ordenes = cursor.fetchone()[0] or 0
            
            if total_tabla_ordenes == 0:
                cursor.execute("PRAGMA table_info(ordenes_trabajo)")
                cols_ot = [info[1] for info in cursor.fetchall()]
                col_monto_ot = 'monto_presupuesto' if 'monto_presupuesto' in cols_ot else 'monto_total'
                if col_monto_ot in cols_ot:
                    cursor.execute(f"SELECT SUM({col_monto_ot}) FROM ordenes_trabajo")
                    total_tabla_ordenes = cursor.fetchone()[0] or 0

            pend = total_tabla_ordenes
            coba = 0
        else:
            pend = res_pend
            coba = res_coba

        total_pagos_db = coba + pend
        
        cursor.execute("SELECT SUM(costo_insumos) FROM ordenes")
        res_tc = cursor.fetchone()[0]
        total_costos_db = res_tc if res_tc is not None else 0
        
        cursor.execute("""
            SELECT strftime('%Y-%m', fecha_vencimiento) as Mes, SUM(monto_cuota) as Total 
            FROM pagos 
            WHERE LOWER(TRIM(estado)) = 'pagado' AND fecha_vencimiento IS NOT NULL 
            GROUP BY Mes ORDER BY Mes
        """)
        rows_hist = cursor.fetchall()
        df_hist = pd.DataFrame(rows_hist, columns=['Mes', 'Total']) if rows_hist else pd.DataFrame(columns=['Mes', 'Total'])

        cursor.execute("""
            SELECT strftime('%Y-%m', fecha_vencimiento) as Mes, SUM(monto_cuota) as Total 
            FROM pagos 
            WHERE LOWER(TRIM(estado)) = 'pendiente' AND fecha_vencimiento IS NOT NULL 
            GROUP BY Mes ORDER BY Mes
        """)
        rows_mes = cursor.fetchall()
        df_mes = pd.DataFrame(rows_mes, columns=['Mes', 'Total']) if rows_mes else pd.DataFrame(columns=['Mes', 'Total'])

    return pend, coba, total_pagos_db, total_costos_db, cant_activas, df_hist, df_mes

@st.cache_data(ttl=30)
def py_cargar_dashboard():
    return _fetch_dashboard_data()

def ejecutar_render_modulo(modulo, nombre_modulo="El módulo"):
    if modulo is None:
        st.warning(f"⚠️ No se encontró el módulo `{nombre_modulo}`.")
        return
    for func_name in ["render", "main", "app", "mostrar"]:
        if hasattr(modulo, func_name):
            getattr(modulo, func_name)()
            return
    st.info(f"El módulo `{nombre_modulo}` está cargado correctamente.")

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
    "🛠️ Herramientas de Mantenimiento",
    "⚙️ Configuración / Mi Negocio",
]
choice = st.sidebar.selectbox("Ir a:", menu)

if choice == "📊 Dashboard":
    st.title("Resumen Ejecutivo")
    
    if st.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()

    pend, coba, total_pagos_db, total_costos_db, cant_activas, df_hist, df_mes = py_cargar_dashboard()

    utilidad_proyectada = total_pagos_db - total_costos_db

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Por Cobrar", f"{int(pend):,} Gs.".replace(",", "."))
    c2.metric("Ya Cobrado", f"{int(coba):,} Gs.".replace(",", "."))
    c3.metric(
        "Utilidad Neta Proyectada",
        f"{int(utilidad_proyectada):,} Gs.".replace(",", "."),
    )
    c4.metric("Órdenes Activas", cant_activas)

    st.divider()

    st.subheader("📈 Ingresos Reales por Mes (Histórico)")
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
        st.info("Aún no hay cobros marcados como 'Pagado' para mostrar en el historial.")

    st.subheader("🗓️ Proyección de Cobros Futuros")
    if not df_mes.empty:
        fig = px.line(
            df_mes,
            x="Mes",
            y="Total",
            title="Flujo de Caja Pendiente",
            markers=True,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay proyecciones de cobros pendientes registradas.")

elif choice == "🛠️ Recepción de Equipos (Taller)":
    from modules.recepcion_equipos import render
    render(get_connection)

elif choice == "🗓️ Cobros Pendientes":
    from modules.cobros_pendientes import render
    render(get_connection)

elif choice == "👥 Gestión de Clientes":
    from modules.clientes import render
    render(get_connection)

elif choice == "📝 Órdenes de Trabajo":
    from modules.ordenes_trabajo import render
    render(get_connection)

elif choice == "📄 Presupuestos Express":
    ejecutar_render_modulo(presupuestos, "presupuestos")

elif choice == "🔔 Recordatorios":
    if recordatorios and hasattr(recordatorios, "render"):
        recordatorios.render(get_connection)
    else:
        ejecutar_render_modulo(recordatorios, "Recordatorios")

elif choice == "✅ Historial de Cobrados":
    from modules.historial_cobrados import render
    render(get_connection)

elif choice == "🛒 Nueva Venta / Servicio":
    from modules.nueva_venta import render
    render(get_connection)

elif choice == "📈 Reportes Avanzados":
    from modules.reportes_avanzados import render
    render(get_connection)

elif choice == "📦 Inventario / Stock":
    from modules.inventario_stock import render
    render(get_connection)

elif choice == "🛠️ Herramientas de Mantenimiento":
    from modules.herramientas_mantenimiento import render as render_herramientas
    render_herramientas(get_connection)

elif choice == "⚙️ Configuración / Mi Negocio":
    ejecutar_render_modulo(mi_negocio, "Mi Negocio / Configuración")