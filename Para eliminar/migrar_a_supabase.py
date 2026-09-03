import sqlite3
import os
import streamlit as st
from supabase import create_client

# Cargar credenciales
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

LOCAL_DB = "database/sistema.db"

def migrar():
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()

    # Obtener todas las tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tablas = [t[0] for t in cursor.fetchall() if t[0] not in ('sqlite_sequence', 'sqlite_stat1')]

    for tabla in tablas:
        print(f"Migrando tabla: {tabla}...")
        
        # Obtener datos y columnas
        cursor.execute(f"SELECT * FROM {tabla}")
        filas = cursor.fetchall()
        cursor.execute(f"PRAGMA table_info({tabla})")
        columnas = [info[1] for info in cursor.fetchall()]

        # Preparar los datos para Supabase (lista de diccionarios)
        for fila in filas:
            datos_fila = dict(zip(columnas, fila))
            # Insertar en Supabase
            try:
                supabase.table(tabla).insert(datos_fila).execute()
            except Exception as e:
                print(f" - Error en {tabla}: {e}")
    
    conn.close()
    print("✅ ¡Migración finalizada! Tus datos ya están en la nube.")

if __name__ == "__main__":
    migrar()