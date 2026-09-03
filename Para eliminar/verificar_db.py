import sqlite3
import os

DB_PATH = "database/sistema.db"

def verificar_columnas():
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: No se encontró el archivo en {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        tablas_a_verificar = ["pagos", "clientes"]
        
        for tabla in tablas_a_verificar:
            print(f"--- Columnas en tabla '{tabla}' ---")
            cursor.execute(f"PRAGMA table_info({tabla})")
            columnas = [col[1] for col in cursor.fetchall()]
            for col in columnas:
                print(f"- {col}")
            print("\n")

        conn.close()
    except Exception as e:
        print(f"❌ Error al consultar la base de datos: {e}")

if __name__ == "__main__":
    verificar_columnas()