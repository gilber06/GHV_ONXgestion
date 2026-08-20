import streamlit as st
from supabase import create_client

# Cargar credenciales desde tus secretos
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# Definición para Supabase (PostgreSQL)
# Nota: PostgreSQL usa SERIAL para auto-incrementar en lugar de AUTOINCREMENT
def crear_tabla_nube():
    # En Supabase, las tablas se gestionan mejor desde su editor o vía migración SQL.
    # Pero para pruebas rápidas, puedes ir al "SQL Editor" en tu panel de Supabase
    # y pegar este código:
    
    query = """
    CREATE TABLE IF NOT EXISTS ordenes_trabajo (
        id_orden SERIAL PRIMARY KEY,
        id_cliente INTEGER NOT NULL,
        tipo_equipo TEXT NOT NULL,
        marca_modelo TEXT NOT NULL,
        numero_serie TEXT,
        accesorios TEXT,
        falla_reportada TEXT NOT NULL,
        diagnostico_tecnico TEXT,
        monto_presupuesto NUMERIC DEFAULT 0.00,
        estado TEXT DEFAULT 'Pendiente de Revisión',
        fecha_ingreso TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        fecha_modificacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    print("Copia el código de arriba y pégalo en el 'SQL Editor' de tu panel de Supabase.")

if __name__ == "__main__":
    crear_tabla_nube()