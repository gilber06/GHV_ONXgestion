import os
import sqlite3

# Ruta absoluta basada en la ubicación del archivo db.py dentro de la carpeta database/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sistema.db")

def get_connection():
    """Conexión centralizada y única a sistema.db para todo el sistema."""
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn