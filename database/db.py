import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# Si existe la URL de Turso en el .env, usamos Turso Cloud. Si no, SQLite local.
USE_TURSO = bool(os.getenv("TURSO_DATABASE_URL"))

if USE_TURSO:
    import turso_db

LOCAL_DB_PATH = os.path.join("database", "sistema.db")

def query(sql, params=None):
    """
    Ejecuta consultas de SELECT y retorna todas las filas.
    """
    if params is None:
        params = []

    if USE_TURSO:
        return turso_db.execute_query_sync(sql, params)
    else:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        res = cursor.fetchall()
        conn.close()
        return res

def execute(sql, params=None):
    """
    Ejecuta INSERT, UPDATE, DELETE o CREATE TABLE.
    """
    if params is None:
        params = []

    if USE_TURSO:
        return turso_db.execute_query_sync(sql, params)
    else:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        conn.close()