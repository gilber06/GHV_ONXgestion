import os
import streamlit as st
from supabase import create_client, Client

# Obtener credenciales desde los secretos de Streamlit o variables de entorno
url = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", "https://ccxtzzkgazgpzacpxdrz.supabase.co"))
key = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY", ""))

supabase: Client = create_client(url, key)

def query(sql, params=None):
    """
    Simulador básico compatible para mantener tus consultas SELECT actuales.
    """
    # Si usas consultas personalizadas, aquí las adaptamos o consultamos directamente las tablas.
    # Por ahora, un placeholder inteligente para tus consultas:
    pass

def execute(sql, params=None):
    """
    Simulador para inserciones y actualizaciones.
    """
    pass