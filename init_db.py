import os
import libsql_client
from dotenv import load_dotenv

load_dotenv()

# Usamos la URL formateada con https://
url = os.getenv("TURSO_DATABASE_URL", "libsql://onxpert-software-gilber06.aws-us-east-1.turso.io")
token = os.getenv("TURSO_AUTH_TOKEN", "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODY3MzExMTgsImlkIjoiMDFhMDAwZGMtNTUwMS03NGE4LWIzOTUtZTYzODU5NDBmNWNlIiwia2lkIjoiQ3NGcF90em1ueXJDUTFqWGozUVNkVW5nMU5Ca3IwZ2NZWW1OSFUwQlp2VSIsInJpZCI6ImEyY2IxMDE3LWQ4YWUtNDhiYi1iMzczLTY0MzJjZWJmNDBlMiJ9.xs2xasvcch3MuZ6IDZM_wZ9H-WalDgtVfyYaUNozJyMUMy_NT_N3MYEpOb2aLaiK8BJDv9tM8FfDuhEi0g3JCw")

# Reemplazamos cualquier protocolo por https://
if "turso.io" in url:
    base_domain = url.split("://")[-1]
    url_http = f"https://{base_domain}"
else:
    url_http = url

print(f"🔍 Conectando vía HTTP a: {url_http}")

try:
    # Conexión sincrónica usando HTTP
    client = libsql_client.create_client_sync(url=url_http, auth_token=token)

    # 1. Crear tabla usuarios
    client.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        nombre_cliente TEXT,
        estado TEXT DEFAULT 'ACTIVO'
    );
    """)

    # 2. Insertar usuario admin
    client.execute("""
    INSERT OR IGNORE INTO usuarios (username, password_hash, nombre_cliente, estado) 
    VALUES (
        'admin', 
        '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 
        'GHV - Service Admin', 
        'ACTIVO'
    );
    """)

    print("\n✅ ¡Éxito! Tabla 'usuarios' creada y usuario 'admin' listo.")

except Exception as e:
    print(f"\n❌ Error de conexión: {e}")