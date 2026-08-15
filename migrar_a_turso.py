import os
import sqlite3
import asyncio
from dotenv import load_dotenv
import libsql_client

# Cargar variables del .env
load_dotenv()

raw_url = os.getenv("TURSO_DATABASE_URL", "")
auth_token = os.getenv("TURSO_AUTH_TOKEN", "")

# Forzar protocolo HTTPS
url = raw_url.replace("libsql://", "https://") if raw_url.startswith("libsql://") else raw_url

# Ruta a la base de datos local
LOCAL_DB_PATH = os.path.join("database", "sistema.db") 

async def migrar():
    if not os.path.exists(LOCAL_DB_PATH):
        print(f"❌ No se encontró la base de datos local en: {LOCAL_DB_PATH}")
        print("Verifica si el archivo .db está en la carpeta 'database' o si tiene otro nombre.")
        return

    print("🔄 Leyendo estructura y datos locales de SQLite...")
    
    local_conn = sqlite3.connect(LOCAL_DB_PATH)
    local_cursor = local_conn.cursor()

    # Extraer DDL de las tablas
    local_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_sql = local_cursor.fetchall()

    # Nombres de las tablas
    local_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in local_cursor.fetchall()]

    async with libsql_client.create_client(url=url, auth_token=auth_token) as client:
        print("🚀 Recreando tablas en Turso Cloud...")
        for sql in tables_sql:
            if sql[0]:
                try:
                    await client.execute(sql[0])
                except Exception as e:
                    print(f"  ⚠️ Nota en tabla: {e}")

        print("📦 Transfiriendo registros...")
        for table in tables:
            # Omitir tabla de prueba si existiera
            if table == "prueba_conexion":
                continue

            local_cursor.execute(f"SELECT * FROM {table};")
            rows = local_cursor.fetchall()
            
            if not rows:
                continue

            local_cursor.execute(f"PRAGMA table_info({table});")
            cols = [col[1] for col in local_cursor.fetchall()]
            
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders});"

            print(f"  ➡️ Migrando {len(rows)} filas de '{table}'...")
            for row in rows:
                try:
                    await client.execute(query, list(row))
                except Exception:
                    # Evitar colisiones si ya hay registros idénticos
                    pass

    local_conn.close()
    print("\n✅ ¡Migración a la nube completada con éxito!")

if __name__ == "__main__":
    asyncio.run(migrar())