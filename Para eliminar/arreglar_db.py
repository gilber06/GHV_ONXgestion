import sqlite3
import os

DB_PATH = "sistema.db"

def agregar_columna_es_companero():
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: No se encontró el archivo {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Obtener lista de columnas actuales
        cursor.execute("PRAGMA table_info(clientes)")
        columnas = [col[1] for col in cursor.fetchall()]

        # 2. Verificar si la columna ya existe
        if "es_companero" not in columnas:
            cursor.execute("ALTER TABLE clientes ADD COLUMN es_companero INTEGER DEFAULT 0;")
            conn.commit()
            print("✅ Columna 'es_companero' agregada exitosamente a la tabla 'clientes'.")
        else:
            print("ℹ️ La columna 'es_companero' ya existe en la tabla 'clientes'.")

        conn.close()
    except Exception as e:
        print(f"❌ Error al modificar la base de datos: {e}")

if __name__ == "__main__":
    agregar_columna_es_companero()