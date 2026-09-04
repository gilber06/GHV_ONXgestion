import sqlite3

conn = sqlite3.connect("database/sistema.db")
cursor = conn.cursor()

# Vuelve a escribir la nota que necesites en el ID correspondiente
cursor.execute(
    "UPDATE pagos SET notas = 'MEMBRESÍA MES 1/3' WHERE id = 92",
)

conn.commit()
conn.close()
print("¡Nota restaurada!")