import os
import sqlite3
from supabase import create_client, Client

# --- CONFIGURACIÓN ---
SUPABASE_URL = "https://ccxtzzkgazgpzacpxdrz.supabase.co"
SUPABASE_KEY = "sb_publishable_hUzqloO9eM7cg-E0ViaWOw_DKOamIj_"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_LOCAL_PATH = os.path.join(BASE_DIR, "database", "sistema.db")

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
        print("⚠️ Sin conexión. Se omitió la sincronización.")
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    conn = sqlite3.connect(DB_LOCAL_PATH)
    cursor = conn.cursor()

    try:
        # -------------------------------------------------------------
        # 1. SUBIR LOCAL -> NUBE (Registros con sincronizado = 0)
        # -------------------------------------------------------------
        cursor.execute(f"SELECT * FROM {nombre_tabla} WHERE sincronizado = 0")
        filas = cursor.fetchall()
        
        # Obtenemos los nombres de las columnas de la tabla local
        cursor.execute(f"PRAGMA table_info({nombre_tabla})")
        columnas_info = cursor.fetchall()
        nombres_columnas = [col[1] for col in columnas_info]

        for fila in filas:
            datos_dict = dict(zip(nombres_columnas, fila))
            # No enviamos la columna de control 'sincronizado' a la nube
            datos_dict.pop('sincronizado', None)

            # Subimos o actualizamos en Supabase
            supabase.table(nombre_tabla).upsert(datos_dict).execute()

            # Marcamos como sincronizado en local (1)
            col_id = 'id_orden' if 'id_orden' in datos_dict else 'id'
            id_registro = datos_dict.get(col_id)
            cursor.execute(f"UPDATE {nombre_tabla} SET sincronizado = 1 WHERE {col_id} = ?", (id_registro,))
        
        conn.commit()

        # -------------------------------------------------------------
        # 2. BAJAR NUBE -> LOCAL
        # -------------------------------------------------------------
        respuesta = supabase.table(nombre_tabla).select("*").execute()
        registros_nube = respuesta.data

        for reg in registros_nube:
            col_id = 'id_orden' if 'id_orden' in reg else 'id'
            id_val = reg.get(col_id)
            
            if id_val is None:
                continue

            # Verificamos si existe en local y su estado de sincronización
            cursor.execute(f"SELECT sincronizado FROM {nombre_tabla} WHERE {col_id} = ?", (id_val,))
            resultado_local = cursor.fetchone()

            if resultado_local is None:
                # A) El registro NO existe en local -> Lo insertamos
                # Añadimos 'sincronizado' = 1 porque viene directamente de la nube sincronizado
                cols = list(reg.keys())
                valores = list(reg.values())
                
                if 'sincronizado' not in cols:
                    cols.append('sincronizado')
                    valores.append(1)

                placeholders = ", ".join(["?"] * len(valores))
                cols_str = ", ".join(cols)
                
                cursor.execute(f"INSERT INTO {nombre_tabla} ({cols_str}) VALUES ({placeholders})", valores)
            
            else:
                # B) El registro SÍ existe en local
                estado_sincronizado = resultado_local[0]
                
                # Solo actualizamos desde la nube si el registro local YA ESTÁ SINCRONIZADO (1).
                # Si está en (0), significa que fue modificado offline localmente y evitamos pisarlo.
                if estado_sincronizado == 1:
                    set_clause = ", ".join([f"{k} = ?" for k in reg.keys() if k != col_id])
                    valores = [v for k, v in reg.items() if k != col_id]
                    valores.append(id_val) # Para el WHERE
                    
                    if set_clause:
                        cursor.execute(f"UPDATE {nombre_tabla} SET {set_clause} WHERE {col_id} = ?", valores)
        
        conn.commit()
        print(f"✅ Tabla '{nombre_tabla}' sincronizada exitosamente.")

    except Exception as e:
        print(f"❌ Error al sincronizar {nombre_tabla}: {e}")
    finally:
        conn.close()

def ejecutar_sincronizacion_completa():
    """Sincroniza todas las tablas de tu sistema"""
    tablas = ["clientes", "negocios", "ordenes", "pagos", "productos", "ordenes_trabajo", "ventas_articulos"]
    for t in tablas:
        sincronizar_tabla(t)