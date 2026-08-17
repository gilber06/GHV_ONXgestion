import os
import sqlite3
import streamlit as st

# Intentar obtener las credenciales de Turso desde los Secrets de Streamlit o variables de entorno
turso_url = None
auth_token = None

try:
    if "TURSO_DATABASE_URL" in st.secrets:
        turso_url = st.secrets["TURSO_DATABASE_URL"]
    if "TURSO_AUTH_TOKEN" in st.secrets:
        auth_token = st.secrets["TURSO_AUTH_TOKEN"]
except Exception:
    pass

if not turso_url:
    turso_url = os.getenv("TURSO_DATABASE_URL")
if not auth_token:
    auth_token = os.getenv("TURSO_AUTH_TOKEN")

USE_TURSO = bool(turso_url and auth_token)

if USE_TURSO:
    import turso_db

LOCAL_DB_PATH = os.path.join("database", "sistema.db")

def query(sql, params=None):
    if params is None:
        params = []
    if USE_TURSO:
        return turso_db.execute_query_sync(sql, params)
    else:
        if not os.path.exists(LOCAL_DB_PATH):
            st.error("⚠️ Turso no está configurado en los Secrets de Streamlit y no hay base de datos local.")
            return []
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        res = cursor.fetchall()
        conn.close()
        return res

def execute(sql, params=None):
    if params is None:
        params = []
    if USE_TURSO:
        return turso_db.execute_query_sync(sql, params)
    else:
        if not os.path.exists(LOCAL_DB_PATH):
            st.error("⚠️ Turso no está configurado en los Secrets de Streamlit y no hay base de datos local.")
            return []
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        conn.close()