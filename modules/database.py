import sqlite3
import os
from pathlib import Path
from sincronizador import ejecutar_sincronizacion_completa

# Intentamos importar libsql para soportar Turso en la nube
try:
    import libsql
    LIBSQL_DISPONIBLE = True
except ImportError:
    LIBSQL_DISPONIBLE = False

# Variables de entorno para Turso (si están configuradas)
TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

# Determina la ruta raíz del proyecto de forma inteligente
RUTA_ACTUAL = Path(__file__).resolve()
BASE_DIR = (
    RUTA_ACTUAL.parent.parent
    if RUTA_ACTUAL.parent.name == "modules"
    else RUTA_ACTUAL.parent
)
DB_PATH = BASE_DIR / "database" / "sistema.db"


def get_connection():
    """
    Retorna una conexión a la base de datos de forma inteligente:
    - Si detecta credenciales de Turso y la librería, conecta a la nube.
    - Si no, utiliza el archivo SQLite local de siempre.
    """
    if TURSO_URL and TURSO_TOKEN and LIBSQL_DISPONIBLE:
        return libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(DB_PATH)


def inicializar_bd():
    # Obtenemos la conexión (local o nube de forma transparente)
    conn = get_connection()
    cursor = conn.cursor()

    # 1. TABLAS PRINCIPALES (Con columna sincronizado añadida)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS negocios (
            id INTEGER PRIMARY KEY, 
            nombre TEXT,
            sincronizado INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY, 
            nombre TEXT, 
            apodo TEXT, 
            telefono TEXT, 
            ruc_ci TEXT,
            activo INTEGER DEFAULT 1,
            es_companero BOOLEAN,
            sincronizado INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ordenes (
            id INTEGER PRIMARY KEY, 
            negocio_id INTEGER, 
            cliente_id INTEGER, 
            descripcion TEXT, 
            fecha_ingreso DATE, 
            monto_total REAL, 
            costo_insumos REAL DEFAULT 0, 
            estado TEXT,
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY(negocio_id) REFERENCES negocios(id),
            FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY, 
            orden_id INTEGER, 
            monto_cuota REAL, 
            fecha_vencimiento DATE, 
            estado_pago TEXT,
            notas TEXT,
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY(orden_id) REFERENCES ordenes(id)
        )
    """)

    # 2. TABLA TALLER / RECEPCIÓN
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ordenes_trabajo (
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
            sincronizado INTEGER DEFAULT 0,
            FOREIGN KEY(id_cliente) REFERENCES clientes(id)
        )
    """)

    # 3. TABLA INVENTARIO / PRODUCTOS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            categoria TEXT, 
            marca TEXT, 
            capacidad_especificacion TEXT, 
            stock INTEGER DEFAULT 0, 
            precio_costo REAL DEFAULT 0, 
            precio_venta REAL DEFAULT 0,
            sincronizado INTEGER DEFAULT 0
        )
    """)

    # 4. DATOS INICIALES POR DEFECTO
    cursor.execute("INSERT OR IGNORE INTO negocios (id, nombre, sincronizado) VALUES (1, 'GHV Service', 0)")
    cursor.execute("INSERT OR IGNORE INTO negocios (id, nombre, sincronizado) VALUES (2, 'OnXpert Software', 0)")

    conn.commit()
    ejecutar_sincronizacion_completa()
    conn.close()
    
    if TURSO_URL and TURSO_TOKEN:
        print("Base de datos inicializada correctamente en la nube (Turso).")
    else:
        print(f"Base de datos local inicializada correctamente en: {DB_PATH}")


if __name__ == "__main__":
    inicializar_bd()