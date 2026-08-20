import sqlite3

DB_LOCAL_PATH = "sistema.db"

tablas = ["clientes", "negocios", "ordenes", "pagos", "productos", "ordenes_trabajo", "ventas_articulos", "historial_eliminacion"]

conn = sqlite3.connect(DB_LOCAL_PATH)
cursor = conn.cursor()

for tabla in tablas:
    try:
        # Intentamos agregar la columna 'sincronizado' (0 = pendiente, 1 = sincronizado)
        cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN sincronizado INTEGER DEFAULT 0")
        print(f"✅ Columna 'sincronizado' agregada a {tabla}")
    except sqlite3.OperationalError:
        # Si la columna ya existía, SQLite da error y simplemente lo ignoramos
        print(f"ℹ️ La tabla {tabla} ya tenía la columna 'sincronizado'")

conn.commit()
conn.close()
print("\n¡Base de datos local lista para sincronizar!")