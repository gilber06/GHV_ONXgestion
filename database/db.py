import os
import sqlite3

LOCAL_DB_PATH = os.path.join("database", "sistema.db")

def query(sql, params=None):
    if params is None:
        params = []
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    res = cursor.fetchall()
    conn.close()
    return res

def execute(sql, params=None):
    if params is None:
        params = []
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    conn.close()