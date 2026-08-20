import sqlite3

# Conectar a tu base de datos local
conn = sqlite3.connect("database/sistema.db")
cursor = conn.cursor()

try:
  # Intentar agregar la columna sincronizado a la tabla clientes
  cursor.execute(
      "ALTER TABLE clientes ADD COLUMN sincronizado INTEGER DEFAULT 0;"
  )
  conn.commit()
  print("¡Éxito! Columna 'sincronizado' agregada a la tabla clientes.")
except Exception as e:
  print("Nota (quizás ya existía):", e)

conn.close()