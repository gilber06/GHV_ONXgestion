import sqlite3

# Conectar a tu base de datos local (ajusta la ruta si está dentro de 'database/')
# Prueba con 'database/sistema.db' o 'sistema.db' según dónde la tengas
conn = sqlite3.connect("database/sistema.db")
cursor = conn.cursor()

tablas = [
    "clientes",
    "negocios",
    "ordenes",
    "pagos",
    "productos",
    "ordenes_trabajo",
    "ventas_articulos",
    "historial_eliminacion",
]

for tabla in tablas:
  try:
    cursor.execute(
        f"ALTER TABLE {tabla} ADD COLUMN sincronizado INTEGER DEFAULT 0;"
    )
    print(f"✅ Columna 'sincronizado' agregada con éxito a la tabla: {tabla}")
  except Exception as e:
    print(f"ℹ️ Tabla {tabla}: {e}")

conn.commit()
conn.close()
print(
    "\n¡Proceso terminado! Ya puedes borrar este archivo 'agregar_columnas.py'."
)