import sqlite3
from datetime import datetime, timedelta

def registrar_venta_completa(cliente_nom, desc_software, monto_software, fechas_software, monto_membresia, cuotas_membresia):
    conn = sqlite3.connect('sistema.db')
    cursor = conn.cursor()
    
    # 1. Asegurar cliente
    cursor.execute("INSERT OR IGNORE INTO clientes (nombre) VALUES (?)", (cliente_nom,))
    cursor.execute("SELECT id FROM clientes WHERE nombre = ?", (cliente_nom,))
    cliente_id = cursor.fetchone()[0]
    
    # 2. Registrar la Orden de OnXpert (ID 2)
    cursor.execute("""INSERT INTO ordenes (negocio_id, cliente_id, descripcion, fecha_ingreso, monto_total, estado) 
                      VALUES (2, ?, ?, ?, ?, 'Activo')""", 
                   (cliente_id, desc_software, datetime.now().date(), monto_software + (monto_membresia * cuotas_membresia)))
    orden_id = cursor.lastrowid
    
    # 3. Registrar los 2 pagos del Software (Mayo y Noviembre)
    for fecha in fechas_software:
        cursor.execute("INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago) VALUES (?, ?, ?, ?)",
                       (orden_id, monto_software/2, fecha, 'Pendiente'))
    
    # 4. Registrar las 10 membresías
    fecha_inicio_membresia = datetime.now().date()
    for i in range(cuotas_membresia):
        vencimiento = fecha_inicio_membresia + timedelta(days=i*30)
        # La primera cuota (i=0) ya te la pagó
        estado = 'Pagado' if i == 0 else 'Pendiente'
        cursor.execute("INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago) VALUES (?, ?, ?, ?)",
                       (orden_id, monto_membresia, vencimiento, estado))
        
    conn.commit()
    conn.close()