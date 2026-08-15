import os
import asyncio
from dotenv import load_dotenv
import libsql_client

# Cargar variables del .env
load_dotenv()

raw_url = os.getenv("TURSO_DATABASE_URL", "")
auth_token = os.getenv("TURSO_AUTH_TOKEN", "")

# Convertir la URL a HTTPS para evitar fallos de WebSockets
if raw_url.startswith("libsql://"):
    url = raw_url.replace("libsql://", "https://")
else:
    url = raw_url

async def main():
    try:
        # Conectar usando HTTPS
        async with libsql_client.create_client(url=url, auth_token=auth_token) as client:
            # Crear tabla de prueba
            await client.execute(
                "CREATE TABLE IF NOT EXISTS prueba_conexion (id INTEGER PRIMARY KEY, mensaje TEXT);"
            )
            
            # Insertar registro
            await client.execute(
                "INSERT INTO prueba_conexion (mensaje) VALUES ('¡Conexión a OnXpert Software exitosa!');"
            )

            # Consultar registros
            rs = await client.execute("SELECT * FROM prueba_conexion;")
            
            print("\n🟢 ¡Conexión exitosa a Turso Cloud!")
            print("Datos en la nube:")
            for row in rs.rows:
                print(row)

    except Exception as e:
        print("\n🔴 Error al conectar con Turso:", e)

if __name__ == "__main__":
    asyncio.run(main())