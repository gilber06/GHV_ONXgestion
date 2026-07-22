import sqlite3

def inicializar_bd():
    conn = sqlite3.connect('sistema.db')
    cursor = conn.cursor()

    cursor.execute('CREATE TABLE IF NOT EXISTS negocios (id INTEGER PRIMARY KEY, nombre TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY, nombre TEXT, apodo TEXT, telefono TEXT, es_companero BOOLEAN)')

    # FÍJATE QUE AQUÍ ESTÉ "costo_insumos"
    cursor.execute('''CREATE TABLE IF NOT EXISTS ordenes 
                      (id INTEGER PRIMARY KEY, negocio_id INTEGER, cliente_id INTEGER, 
                       descripcion TEXT, fecha_ingreso DATE, monto_total REAL, 
                       costo_insumos REAL DEFAULT 0, estado TEXT,
                       FOREIGN KEY(negocio_id) REFERENCES negocios(id))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS pagos 
                      (id INTEGER PRIMARY KEY, orden_id INTEGER, monto_cuota REAL, 
                       fecha_vencimiento DATE, estado_pago TEXT)''')

    cursor.execute("INSERT OR IGNORE INTO negocios (id, nombre) VALUES (1, 'GHV Service')")
    cursor.execute("INSERT OR IGNORE INTO negocios (id, nombre) VALUES (2, 'OnXpert')")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    inicializar_bd()