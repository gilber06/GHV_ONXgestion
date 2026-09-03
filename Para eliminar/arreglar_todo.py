import sqlite3
import os

DB_PATH = "database/sistema.db"

def solucionar():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Agregar 'es_companero' a clientes en la BD correcta
    cursor.execute("PRAGMA table_info(clientes)")
    cols_clientes = [col[1] for col in cursor.fetchall()]
    if "es_companero" not in cols_clientes:
        cursor.execute("ALTER TABLE clientes ADD COLUMN es_companero INTEGER DEFAULT 0;")
        print("✅ Columna 'es_companero' agregada a 'clientes'.")
    else:
        print("ℹ️ 'es_companero' ya existe en 'clientes'.")

    # 2. Ver las columnas reales de 'ordenes_trabajo' para saber cómo se llama su ID
    print("\n--- Columnas de 'ordenes_trabajo' ---")
    cursor.execute("PRAGMA table_info(ordenes_trabajo)")
    for col in cursor.fetchall():
        print(f"- {col[1]}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    solucionar()