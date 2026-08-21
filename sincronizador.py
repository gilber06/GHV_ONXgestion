import os
import sqlite3
from supabase import create_client, Client

# --- CONFIGURACIÓN ---
SUPABASE_URL = "https://ccxtzzkgazgpzacpxdrz.supabase.co"
SUPABASE_KEY = "sb_publishable_hUzqloO9eM7cg-E0ViaWOw_DKOamIj_"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_LOCAL_PATH = os.path.join(BASE_DIR, "database", "sistema.db")

# MAPA DE PRIMARY KEYS: Esto asegura que el script sepa qué buscar en cada tabla
PK_MAP = {
    "clientes": "id",
    "negocios": "id",
    "ordenes": "id_orden",
    "pagos": "id_pago",
    "productos": "id",
    "ordenes_trabajo": "id_orden_trabajo",
    "ventas_articulos": "id_venta"
}

def hay_conexion():
    """Verifica de forma rápida si hay internet"""
    import socket
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

def sincronizar_tabla(nombre_tabla):
    if not hay_conexion():
        return

    # Obtener el nombre del ID para esta tabla, si no existe en el mapa, por defecto es 'id'
    col_id = PK_MAP.get(nombre_tabla, 'id')
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    conn = sqlite3.connect(DB_LOCAL_PATH)
    cursor = conn.cursor()

    try:
        # 1. SUBIR LOCAL -> NUBE (Registros con sincronizado = 0)
        cursor.execute(f"SELECT * FROM {nombre_tabla} WHERE sincronizado = 0 OR sincronizado IS NULL")
        filas = cursor.fetchall()
        cursor.execute(f"PRAGMA table_info({nombre_tabla})")
        nombres_columnas = [col[1] for col in cursor.fetchall()]

        for fila in filas:
            datos_dict = dict(zip(nombres_columnas, fila))
            # Quitamos la columna de control para enviar a Supabase
            if 'sincronizado' in datos_dict:
                datos_dict.pop('sincronizado')

            # Upsert a Supabase
            supabase.table(nombre_tabla).upsert(datos_dict).execute()

            # Marcamos local como sincronizado
            id_val = datos_dict.get(col_id)
            cursor.execute(f"UPDATE {nombre_tabla} SET sincronizado = 1 WHERE {col_id} = ?", (id_val,))
        
        conn.commit()

        # 2. BAJAR NUBE -> LOCAL (Actualizar cambios de la nube a local)
        respuesta = supabase.table(nombre_tabla).select("*").execute()
        registros_nube = respuesta.data

        for reg in registros_nube:
            id_val = reg.get(col_id)
            if id_val is None: continue

            # Verificar si existe en local
            cursor.execute(f"SELECT sincronizado FROM {nombre_tabla} WHERE {col_id} = ?", (id_val,))
            res = cursor.fetchone()

            if res is None:
                # Insertar nuevo registro desde nube
                cols = list(reg.keys())
                valores = list(reg.values())
                if 'sincronizado' not in cols:
                    cols.append('sincronizado')
                    valores.append(1)
                
                placeholders = ", ".join(["?"] * len(valores))
                cursor.execute(f"INSERT INTO {nombre_tabla} ({', '.join(cols)}) VALUES ({placeholders})", valores)
            
            else:
                # Actualizar si local ya estaba sincronizado (evita pisar cambios locales offline)
                if res[0] == 1:
                    set_clause = ", ".join([f"{k} = ?" for k in reg.keys() if k != col_id])
                    valores = [v for k, v in reg.items() if k != col_id]
                    valores.append(id_val)
                    cursor.execute(f"UPDATE {nombre_tabla} SET {set_clause} WHERE {col_id} = ?", valores)
        
        conn.commit()
        print(f"✅ Tabla '{nombre_tabla}' sincronizada.")

    except Exception as e:
        print(f"❌ Error en {nombre_tabla}: {e}")
    finally:
        conn.close()

def ejecutar_sincronizacion_completa():
    tablas = ["clientes", "negocios", "ordenes", "pagos", "productos", "ordenes_trabajo", "ventas_articulos"]
    for t in tablas:
        sincronizar_tabla(t)
    print("🚀 Sincronización completa finalizada.")