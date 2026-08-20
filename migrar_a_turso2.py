import os
import sqlite3

# Leer .streamlit/secrets.toml manualmente sin librerías externas
secrets_path = os.path.join(".streamlit", "secrets.toml")
if os.path.exists(secrets_path):
    print("🔑 Leyendo credenciales de .streamlit/secrets.toml...")
    with open(secrets_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ[key] = val

import turso_db

LOCAL_DB = "database/sistema.db"

def migrar():
    if not os.path.exists(LOCAL_DB):
        print(f"❌ Error: No se encuentra el archivo local {LOCAL_DB}")
        return

    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tablas = cursor.fetchall()

    for tabla in tablas:
        nombre_tabla = tabla[0]
        if nombre_tabla in ('sqlite_sequence', 'sqlite_stat1'): 
            continue

        print(f"📦 Migrando tabla: {nombre_tabla}...")
        
        cursor.execute(f"SELECT * FROM {nombre_tabla}")
        filas = cursor.fetchall()
        
        if not filas:
            print(f" - La tabla {nombre_tabla} está vacía localmente. Saltando...")
            continue

        cursor.execute(f"PRAGMA table_info({nombre_tabla})")
        columnas = [info[1] for info in cursor.fetchall()]
        
        for fila in filas:
            placeholders = ", ".join(["?"] * len(columnas))
            cols_str = ", ".join(columnas)
            sql = f"INSERT OR IGNORE INTO {nombre_tabla} ({cols_str}) VALUES ({placeholders})"
            
            try:
                turso_db.execute_query_sync(sql, list(fila))
            except Exception as e:
                print(f" - ⚠️ Error al insertar en {nombre_tabla}: {e}")

    conn.close()
    print("✅ ¡Migración finalizada con éxito!")

if __name__ == "__main__":
    migrar()