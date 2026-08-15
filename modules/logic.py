from datetime import datetime, timedelta
from pathlib import Path
from modules.database import get_connection  # Importa la conexión híbrida centralizada

def registrar_venta_completa(
    cliente_nom,
    desc_software,
    monto_software,
    fechas_software,
    monto_membresia,
    cuotas_membresia,
    negocio_id=2  # Por defecto 2: OnXpert Software
):
    """
    Registra una venta completa (Software + Membresía recurrente) utilizando la conexión híbrida.
    Retorna el ID de la orden generada.
    """
    try:
        # El bloque 'with' maneja la conexión mediante get_connection()
        with get_connection() as conn:
            cursor = conn.cursor()

            # 1. Asegurar cliente y obtener su ID
            cursor.execute(
                "INSERT OR IGNORE INTO clientes (nombre) VALUES (?)",
                (cliente_nom,),
            )
            cursor.execute(
                "SELECT id FROM clientes WHERE nombre = ?", (cliente_nom,)
            )
            res_cliente = cursor.fetchone()
            
            if not res_cliente:
                raise ValueError(f"No se pudo obtener el ID del cliente: {cliente_nom}")
            
            cliente_id = res_cliente[0]

            # 2. Registrar la Orden de Venta
            monto_total_orden = monto_software + (monto_membresia * cuotas_membresia)
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")

            cursor.execute(
                """INSERT INTO ordenes (negocio_id, cliente_id, descripcion, fecha_ingreso, monto_total, estado) 
                   VALUES (?, ?, ?, ?, ?, 'Activo')""",
                (negocio_id, cliente_id, desc_software, fecha_hoy, monto_total_orden),
            )
            
            # Obtener el lastrowid de manera segura según el tipo de conexión (SQLite local vs Turso)
            if hasattr(cursor, "lastrowid") and cursor.lastrowid:
                orden_id = cursor.lastrowid
            else:
                cursor.execute("SELECT MAX(id) FROM ordenes")
                orden_id = cursor.fetchone()[0]

            # 3. Registrar los pagos del Software (dividido entre las fechas indicadas)
            cant_cuotas_sw = len(fechas_software) if fechas_software else 1
            monto_cuota_sw = monto_software / cant_cuotas_sw

            for idx, fecha in enumerate(fechas_software, 1):
                cursor.execute(
                    """INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas) 
                       VALUES (?, ?, ?, 'Pendiente', ?)""",
                    (
                        orden_id,
                        monto_cuota_sw,
                        str(fecha),
                        f"Software - Pago {idx}/{cant_cuotas_sw}",
                    ),
                )

            # 4. Registrar las cuotas de membresía
            fecha_inicio = datetime.now().date()
            for i in range(cuotas_membresia):
                vencimiento = (fecha_inicio + timedelta(days=i * 30)).strftime("%Y-%m-%d")
                
                # La primera cuota (i=0) se marca como cobrada inmediatamente
                estado = "Pagado" if i == 0 else "Pendiente"
                
                cursor.execute(
                    """INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago, notas) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        orden_id,
                        monto_membresia,
                        vencimiento,
                        estado,
                        f"Membresía - Cuota {i+1}/{cuotas_membresia}",
                    ),
                )

            conn.commit()
            print(f" Venta #{orden_id} registrada con éxito para '{cliente_nom}'.")
            return orden_id

    except Exception as e:
        print(f"❌ Error al registrar la venta: {e}")
        return None


# --- Prueba de ejecución directa ---
if __name__ == "__main__":
    # Ejemplo de uso:
    id_generado = registrar_venta_completa(
        cliente_nom="CODIG SA",
        desc_software="Licencia OnXpert Taller + Módulo Tickets",
        monto_software=1500000,
        fechas_software=["2026-05-15", "2026-11-15"],
        monto_membresia=150000,
        cuotas_membresia=10,
    )