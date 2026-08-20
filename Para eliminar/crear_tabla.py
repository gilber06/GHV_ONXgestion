import os
from pathlib import Path
import sqlite3
from modules.database import get_connection  # Importa la conexión centralizada[cite: 10]

def crear_tabla_ordenes():
    # Determinación de rutas para mostrar por consola
    RUTA_ACTUAL = Path(__file__).resolve()
    BASE_DIR = RUTA_ACTUAL.parent.parent if RUTA_ACTUAL.parent.name == "modules" else RUTA_ACTUAL.parent
    DB_PATH = BASE_DIR / "database" / "sistema.db"

    # Conexión usando el conector centralizado[cite: 10]
    with get_connection() as conn:
        cursor = conn.cursor()

        # Script de creación de la tabla de recepción de equipos[cite: 10]
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordenes_trabajo (
            id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER NOT NULL,
            tipo_equipo TEXT NOT NULL,
            marca_modelo TEXT NOT NULL,
            numero_serie TEXT,
            accesorios TEXT,
            falla_reportada TEXT NOT NULL,
            diagnostico_tecnico TEXT,
            monto_presupuesto REAL DEFAULT 0.00,
            estado TEXT DEFAULT 'Pendiente de Revisión',
            fecha_ingreso DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_modificacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(id_cliente) REFERENCES clientes(id)
        )
        ''')

        conn.commit()

    print(f"¡Tabla ordenes_trabajo verificada/creada con éxito en: {DB_PATH}!")[cite: 10]

if __name__ == "__main__":
    crear_tabla_ordenes()