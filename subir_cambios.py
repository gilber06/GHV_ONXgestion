import sqlite3
import os
from dotenv import load_dotenv
import libsql

load_dotenv()

# Conexión local (donde SÍ están tus cambios)
conn_local = sqlite3.connect("database/sistema.db")
conn_local.row_factory = sqlite3.Row
cursor_local = conn_local.cursor()

# Conexión a Turso (la nube)
url = os.environ.get("TURSO_DATABASE_URL")
token = os.environ.get("TURSO_AUTH_TOKEN")
conn_turso = libsql.connect(database=url, auth_token=token)
cursor_turso = conn_turso.cursor()

print("Sincronizando tabla 'pagos' de local a la nube...")

# Obtenemos todos los pagos de la base de datos local
pagos_locales = cursor_local.execute("SELECT id, orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas FROM pagos").fetchall()

for pago in pagos_locales:
    # Actualizamos o insertamos cada pago en Turso para que coincida exactamente
    cursor_turso.execute("""
        INSERT INTO pagos (id, orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            fecha_vencimiento = excluded.fecha_vencimiento,
            monto_cuota = excluded.monto_cuota,
            estado_pago = excluded.estado_pago,
            notas = excluded.notas
    """, (pago["id"], pago["orden_id"], pago["monto_cuota"], pago["fecha_vencimiento"], pago["estado_pago"], pago["notas"]))

conn_turso.commit()
conn_local.close()
conn_turso.close()

print("¡Listo! Los datos locales se han subido a la nube con éxito.")