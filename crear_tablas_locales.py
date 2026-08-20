import sqlite3
import os

# 1. Revisar si hay otros archivos de base de datos en la carpeta
archivos_db = [f for f in os.listdir('.') if f.endswith(('.db', '.sqlite', '.sqlite3'))]
print(f"📁 Archivos de base de datos encontrados en tu carpeta: {archivos_db}")

# 2. Conectar a sistema.db y crear las 8 tablas locales con la columna 'sincronizado'
conn = sqlite3.connect("sistema.db")
cursor = conn.cursor()

script_tablas = """
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    apodo TEXT,
    telefono TEXT,
    es_companero BOOLEAN DEFAULT 0,
    ruc_ci TEXT,
    activo BOOLEAN DEFAULT 1,
    sincronizado INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS negocios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    sincronizado INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ordenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER,
    cliente_id INTEGER,
    descripcion TEXT,
    fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    monto_total DECIMAL(12, 2),
    costo_insumos DECIMAL(12, 2),
    estado TEXT,
    sincronizado INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pagos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orden_id INTEGER,
    monto_cuota DECIMAL(12, 2),
    fecha_vencimiento DATE,
    estado_pago TEXT,
    notas TEXT,
    sincronizado INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT,
    marca TEXT,
    capacidad_especificacion TEXT,
    stock INTEGER DEFAULT 0,
    precio_costo DECIMAL(12, 2),
    precio_venta DECIMAL(12, 2),
    sincronizado INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ordenes_trabajo (
    id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente INTEGER,
    tipo_equipo TEXT,
    marca_modelo TEXT,
    numero_serie TEXT,
    accesorios TEXT,
    falla_reportada TEXT,
    diagnostico_tecnico TEXT,
    monto_presupuesto DECIMAL(12, 2),
    estado TEXT,
    fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP,
    sincronizado INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ventas_articulos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    producto TEXT,
    tipo_pago TEXT,
    monto_total DECIMAL(12, 2),
    costo_adquisicion DECIMAL(12, 2),
    fecha_venta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sincronizado INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS historial_eliminacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orden_id INTEGER,
    cliente TEXT,
    monto DECIMAL(12, 2),
    detalle TEXT,
    fecha_eliminacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sincronizado INTEGER DEFAULT 0
);
"""

cursor.executescript(script_tablas)
conn.commit()
conn.close()

print("✅ ¡Estructura de tablas locales lista en 'sistema.db'!\n")