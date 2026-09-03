import os
import asyncio
from dotenv import load_dotenv
import libsql_client

load_dotenv()

# Obtener URL y Token desde os.getenv o st.secrets
raw_url = os.getenv("TURSO_DATABASE_URL", "")
auth_token = os.getenv("TURSO_AUTH_TOKEN", "")

if not raw_url or not auth_token:
    try:
        import streamlit as st
        raw_url = raw_url or st.secrets.get("TURSO_DATABASE_URL", "")
        auth_token = auth_token or st.secrets.get("TURSO_AUTH_TOKEN", "")
    except Exception:
        pass

# Asegurar protocolo HTTPS para comunicación estable por API
URL = raw_url.replace("libsql://", "https://") if raw_url.startswith("libsql://") else raw_url

def execute_query_sync(query: str, params=None):
    """
    Ejecuta una consulta SQL en Turso de forma síncrona.
    Retorna una lista de tuplas/filas, compatible con el comportamiento de sqlite3.fetchall().
    """
    if params is None:
        params = []

    async def _run():
        async with libsql_client.create_client(url=URL, auth_token=auth_token) as client:
            res = await client.execute(query, params)
            return [tuple(row) for row in res.rows]

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(_run())
    else:
        return loop.run_until_complete(_run())