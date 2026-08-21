import sqlite3

# Conectamos a tu base de datos en la misma carpeta
conn = sqlite3.connect('sistema.db')
cursor = conn.cursor()

try:
    print("Intentando agregar columna 'notas'...")
    # Agregamos la columna 'nota' a la tabla 'pagos'
    cursor.execute("ALTER TABLE pagos ADD COLUMN notas TEXT")
    conn.commit()
    print("✅ ¡Éxito! Columna 'notas' agregada correctamente.")
except sqlite3.OperationalError as e:
    # Si sale este error, es probable que la columna ya exista
    print(f"⚠️ Aviso: {e}")
finally:
    conn.close()