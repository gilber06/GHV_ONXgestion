import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
try:
    import plotly.express as px
except ImportError:
    st.error("Por favor, instala plotly ejecutando: pip install plotly")

# 1. CONFIGURACIÓN Y PARCHE DE BASE DE DATOS
st.set_page_config(page_title="GHV & OnXpert", layout="wide", page_icon="📈")

def inicializar_db():
    conn = sqlite3.connect('sistema.db')
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS clientes 
                      (id INTEGER PRIMARY KEY, nombre TEXT, apodo TEXT, telefono TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS negocios 
                      (id INTEGER PRIMARY KEY, nombre TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS ordenes 
                      (id INTEGER PRIMARY KEY, negocio_id INTEGER, cliente_id INTEGER, 
                       descripcion TEXT, fecha_ingreso TEXT, monto_total REAL, 
                       costo_insumos REAL DEFAULT 0, estado TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS pagos 
                      (id INTEGER PRIMARY KEY, orden_id INTEGER, monto_cuota REAL, 
                       fecha_vencimiento TEXT, estado_pago TEXT)""")
    
    cursor.execute("PRAGMA table_info(ordenes)")
    columnas = [info[1] for info in cursor.fetchall()]
    if 'costo_insumos' not in columnas:
        cursor.execute("ALTER TABLE ordenes ADD COLUMN costo_insumos REAL DEFAULT 0")
    
    cursor.execute("SELECT COUNT(*) FROM negocios")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO negocios (id, nombre) VALUES (?,?)", [(1, 'GHV-Service'), (2, 'OnXpert Software')])
    
    conn.commit()
    conn.close()

inicializar_db()

# --- 2. FUNCIONES DE LÓGICA ---

def registrar_venta_onxpert(cliente, empresa, telefono, desc, monto_soft, monto_memb, cuotas_memb, fecha_manual):
    conn = sqlite3.connect('sistema.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO clientes (nombre, apodo, telefono) VALUES (?,?,?)", (cliente, empresa, telefono))
    cursor.execute("UPDATE clientes SET apodo = ?, telefono = ? WHERE nombre = ?", (empresa, telefono, cliente))
    cursor.execute("SELECT id FROM clientes WHERE nombre = ?", (cliente,))
    cliente_id = cursor.fetchone()[0]
    
    cursor.execute("INSERT INTO ordenes (negocio_id, cliente_id, descripcion, fecha_ingreso, monto_total, costo_insumos, estado) VALUES (2, ?, ?, ?, ?, 0, 'Activo')",
                   (cliente_id, desc, fecha_manual, monto_soft + (monto_memb * cuotas_memb)))
    orden_id = cursor.lastrowid
    
    pagos_soft = [
        (orden_id, monto_soft/2, f"{fecha_manual.year}-05-06", "Pendiente"), 
        (orden_id, monto_soft/2, f"{fecha_manual.year}-11-06", "Pendiente")
    ]
    cursor.executemany("INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago) VALUES (?,?,?,?)", pagos_soft)
    
    for i in range(cuotas_memb):
        vencimiento = fecha_manual + timedelta(days=i*30) 
        cursor.execute("INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago) VALUES (?,?,?,?)", 
                       (orden_id, monto_memb, vencimiento.strftime("%Y-%m-%d"), 'Pendiente'))
    conn.commit()
    conn.close()

def registrar_service_ghv(cliente, empresa, telefono, equipo, falla, monto_total, costo_repuestos, fecha_manual, cuotas):
    conn = sqlite3.connect('sistema.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO clientes (nombre, apodo, telefono) VALUES (?,?,?)", (cliente, empresa, telefono))
    cursor.execute("UPDATE clientes SET apodo = ?, telefono = ? WHERE nombre = ?", (empresa, telefono, cliente))
    cursor.execute("SELECT id FROM clientes WHERE nombre = ?", (cliente,))
    cliente_id = cursor.fetchone()[0]
    
    cursor.execute("INSERT INTO ordenes (negocio_id, cliente_id, descripcion, fecha_ingreso, monto_total, costo_insumos, estado) VALUES (1, ?, ?, ?, ?, ?, 'En Proceso')", 
                   (cliente_id, f"{equipo} - {falla}", fecha_manual, monto_total, costo_repuestos))
    orden_id = cursor.lastrowid
    
    monto_cuota = monto_total / cuotas
    for i in range(cuotas):
        vencimiento = fecha_manual + timedelta(days=i*30)
        cursor.execute("INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado_pago) VALUES (?, ?, ?, 'Pendiente')", 
                       (orden_id, monto_cuota, vencimiento.strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

# --- 3. INTERFAZ ---

st.sidebar.title("GHV-Service & OnXpert Software")

# --- MARCA DE DESARROLLO AL PIE DE LA SIDEBAR ---
st.sidebar.markdown(
    """
    <style>
        .sidebar-footer {
            position: fixed;
            bottom: 15px;
            width: 15rem;
            text-align: center;
            font-size: 13px;
            color: #555555; /* Gris oscuro para que resalte en fondo claro */
            font-family: 'Segoe UI', sans-serif;
            z-index: 100;
        }
    </style>
    <div class="sidebar-footer">
        <span style="opacity: 0.7;">Desarrollado por</span><br>
        <b style="color: #000000; letter-spacing: 1px;">OnXpert™ Software 2026</b>
    </div>
    """,
    unsafe_allow_html=True
)

menu = ["📊 Dashboard", "🗓️ Cobros Pendientes", "👥 Gestión de Clientes", "📝 Órdenes de Trabajo", "✅ Historial de Cobrados", "➕ Nuevos Registros"]
choice = st.sidebar.selectbox("Ir a:", menu)

conn = sqlite3.connect('sistema.db')

if choice == "📊 Dashboard":
    st.title("Resumen Ejecutivo")
    c1, c2, c3, c4 = st.columns(4)
    pend = pd.read_sql_query("SELECT SUM(monto_cuota) FROM pagos WHERE estado_pago='Pendiente'", conn).iloc[0,0] or 0
    coba = pd.read_sql_query("SELECT SUM(monto_cuota) FROM pagos WHERE estado_pago='Pagado'", conn).iloc[0,0] or 0
    
    # Utilidad Proyectada basada en la realidad de la tabla pagos
    total_pagos_db = pd.read_sql_query("SELECT SUM(monto_cuota) FROM pagos", conn).iloc[0,0] or 0
    total_costos_db = pd.read_sql_query("SELECT SUM(costo_insumos) FROM ordenes", conn).iloc[0,0] or 0
    ganancia_real = total_pagos_db - total_costos_db

    c1.metric("Por Cobrar", f"{pend:,.0f} Gs")
    c2.metric("Ya Cobrado", f"{coba:,.0f} Gs")
    c3.metric("Utilidad Proyectada", f"{ganancia_real:,.0f} Gs")
    c4.metric("Órdenes Activas", len(pd.read_sql_query("SELECT id FROM ordenes WHERE estado != 'Entregado'", conn)))

    st.divider()
    
    # --- GRÁFICOS RESTAURADOS ---
    st.subheader("📈 Ingresos Reales por Mes (Histórico)")
    df_hist = pd.read_sql_query("""
        SELECT strftime('%Y-%m', fecha_vencimiento) as Mes, SUM(monto_cuota) as Total 
        FROM pagos WHERE estado_pago = 'Pagado' GROUP BY Mes ORDER BY Mes
    """, conn)
    if not df_hist.empty:
        fig_h = px.bar(df_hist, x='Mes', y='Total', title="Dinero Cobrado por Mes", color_discrete_sequence=['#2ecc71'])
        st.plotly_chart(fig_h, use_container_width=True)
    else:
        st.info("Aún no hay cobros marcados como 'Pagado' para mostrar en el historial.")

    st.subheader("🗓️ Proyección de Cobros Futuros")
    df_mes = pd.read_sql_query("""
        SELECT strftime('%Y-%m', fecha_vencimiento) as Mes, SUM(monto_cuota) as Total 
        FROM pagos WHERE estado_pago = 'Pendiente' GROUP BY Mes ORDER BY Mes
    """, conn)
    if not df_mes.empty:
        fig = px.line(df_mes, x='Mes', y='Total', title="Flujo de Caja Pendiente", markers=True)
        st.plotly_chart(fig, use_container_width=True)

elif choice == "🗓️ Cobros Pendientes":
    st.title("Control de Cobros")
    
    # 1. Traemos los datos incluyendo el nombre y empresa para agrupar
    df_p = pd.read_sql_query("""
        SELECT p.id as ID, n.nombre as Negocio, c.apodo as Empresa, c.nombre as Contacto, 
               p.monto_cuota as Monto, p.fecha_vencimiento as Vence, o.descripcion as Detalle, c.telefono as Telefono
        FROM pagos p 
        JOIN ordenes o ON p.orden_id = o.id 
        JOIN clientes c ON o.cliente_id = c.id
        JOIN negocios n ON o.negocio_id = n.id 
        WHERE p.estado_pago = 'Pendiente' 
        ORDER BY p.fecha_vencimiento ASC
    """, conn)
        
    if not df_p.empty:
        # 2. Agrupamos por Empresa/Cliente para crear los expanders
        clientes_con_deuda = df_p['Empresa'].unique()
        
        for empresa in clientes_con_deuda:
            # Filtramos los pagos solo de esta empresa
            pagos_cliente = df_p[df_p['Empresa'] == empresa]
            total_deuda_cliente = pagos_cliente['Monto'].sum()
            
            # Creamos el desplegable con el nombre y el total adeudado
            with st.expander(f"🏢 {empresa} - (Total Pendiente: {total_deuda_cliente:,.0f} Gs)"):
                # Mostramos su tabla específica
                st.table(pagos_cliente[['ID', 'Vence', 'Monto', 'Detalle']])
                
                # Botón rápido para cobrar dentro del expander
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    pago_id = st.selectbox(f"ID a cobrar ({empresa}):", pagos_cliente['ID'], key=f"sel_{empresa}")
                    if st.button(f"✅ Cobrar ID {pago_id}", key=f"btn_{empresa}"):
                        conn.execute("UPDATE pagos SET estado_pago = 'Pagado' WHERE id = ?", (pago_id,))
                        conn.commit()
                        st.success(f"Cobro {pago_id} registrado.")
                        st.rerun()
                
                with col_btn2:
                    # WhatsApp rápido para este cliente
                    r_wa = pagos_cliente[pagos_cliente['ID'] == pago_id].iloc[0]
                    msg = f"Hola {r_wa['Contacto']}, te envío el recordatorio de tu cuota de {r_wa['Monto']:,.0f} Gs. ¡Saludos!"
                    tel = str(r_wa['Telefono']).replace(" ", "").replace("+", "")
                    link = f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"
                    st.markdown(f"<br>[📲 Enviar WhatsApp a {empresa}]( {link} )", unsafe_allow_html=True)

    else:
        st.info("No hay cobros pendientes por el momento.")

    # Mantenemos la zona de limpieza abajo por si acaso
    st.markdown("---")
    with st.expander("⚠️ Zona de Limpieza (Solo errores de carga)"):
        id_borrar = st.number_input("ID del pago a eliminar", min_value=0, step=1)
        if st.button("🗑️ Eliminar Permanentemente"):
            conn.execute("DELETE FROM pagos WHERE id = ?", (id_borrar,))
            conn.commit()
            st.rerun()

elif choice == "👥 Gestión de Clientes":
    st.title("Base de Datos de Clientes")
    df_c = pd.read_sql_query("SELECT id, nombre, apodo as Empresa, telefono FROM clientes", conn)
    edited_c = st.data_editor(df_c, use_container_width=True, hide_index=True, num_rows="dynamic")
    if st.button("💾 Actualizar Clientes"):
        for _, r in edited_c.iterrows():
            conn.execute("UPDATE clientes SET nombre=?, apodo=?, telefono=? WHERE id=?", (r['nombre'], r['Empresa'], r['telefono'], r['id']))
        conn.commit()
        st.success("Base de datos de clientes actualizada.")

elif choice == "📝 Órdenes de Trabajo":
    st.title("Generador de Comprobantes (OT)")
    # SQL Corregido para sumar cuotas reales
    df_ot = pd.read_sql_query("""
        SELECT o.id as OT, n.nombre as Negocio, c.nombre as Cliente, c.apodo as Empresa, 
               o.descripcion as Trabajo, SUM(p.monto_cuota) as TotalReal, o.estado as Estado, c.telefono as Tel
        FROM ordenes o 
        JOIN clientes c ON o.cliente_id = c.id 
        JOIN negocios n ON o.negocio_id = n.id 
        JOIN pagos p ON p.orden_id = o.id
        WHERE o.estado != 'Entregado'
        GROUP BY o.id
    """, conn)
    
    if not df_ot.empty:
        st.dataframe(df_ot.drop(columns=['Tel']), use_container_width=True, hide_index=True)
        ot_sel = st.selectbox("Seleccione OT:", df_ot['OT'])
        if st.button("Generar Mensaje de OT"):
            r = df_ot[df_ot['OT'] == ot_sel].iloc[0]
            txt = f"📑 *OT #{r['OT']} - {r['Negocio']}*\nCliente: {r['Cliente']}\nTrabajo: {r['Trabajo']}\nTotal Actualizado: {r['TotalReal']:,.0f} Gs"
            st.code(txt)
            tel_clean = str(r['Tel']).replace(' ','').replace('+','')
            st.markdown(f"[📲 Enviar por WhatsApp](https://wa.me/{tel_clean}?text={urllib.parse.quote(txt)})")
    else: st.info("No hay órdenes de trabajo activas.")

elif choice == "✅ Historial de Cobrados":
    st.title("Registro Histórico de Ingresos")
    # --- HISTORIAL RESTAURADO ---
    df_h = pd.read_sql_query("""
        SELECT p.fecha_vencimiento as Fecha, n.nombre as Negocio, c.nombre as Cliente, c.apodo as Empresa, p.monto_cuota as Cobrado
        FROM pagos p JOIN ordenes o ON p.orden_id = o.id JOIN clientes c ON o.cliente_id = c.id
        JOIN negocios n ON o.negocio_id = n.id WHERE p.estado_pago = 'Pagado' ORDER BY Fecha DESC
    """, conn)
    if not df_h.empty:
        st.dataframe(df_h, use_container_width=True, hide_index=True)
    else:
        st.info("El historial está vacío. Los pagos aparecerán aquí una vez que los confirmes en 'Cobros Pendientes'.")

elif choice == "➕ Nuevos Registros":
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🚀 OnXpert Software")
        with st.form("onx"):
            n, e, t = st.text_input("Contacto"), st.text_input("Empresa"), st.text_input("Teléfono")
            d, ms, mm = st.text_input("Software"), st.number_input("Costo Soft"), st.number_input("Membresía")
            f_m = st.date_input("Fecha de inicio", value=datetime.now().date())
            cant_meses = st.slider("Meses membresía", 1, 12, 10) 
            if st.form_submit_button("Guardar Registro"):
                registrar_venta_onxpert(n, e, t, d, ms, mm, cant_meses, f_m)
                st.success("Software registrado correctamente.")
                st.rerun()
    with c2:
        st.subheader("🔧 GHV-Service")
        with st.form("ghv"):
            n, e, t = st.text_input("Contacto"), st.text_input("Empresa"), st.text_input("Teléfono")
            eq, f, p = st.text_input("Equipo"), st.text_input("Falla"), st.number_input("Precio Final")
            c_rep = st.number_input("Costo Repuestos", min_value=0.0)
            f_m_g = st.date_input("Fecha Servicio", value=datetime.now().date())
            cant_c = st.number_input("Cuotas", min_value=1, value=1)
            if st.form_submit_button("Registrar Servicio"):
                registrar_service_ghv(n, e, t, eq, f, p, c_rep, f_m_g, int(cant_c))
                st.success("Servicio técnico registrado.")
                st.rerun()

conn.close()