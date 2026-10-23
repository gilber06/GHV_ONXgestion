# modules/nueva_venta.py
import streamlit as st
import pandas as pd
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

def registrar_venta_onxpert(get_connection, cliente, empresa, telefono, desc, monto_soft, cuotas_soft, monto_memb, meses_memb, fecha_manual):
    """Función de apoyo para registrar ventas de software o membresías utilizando la conexión híbrida."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar cliente id
        cursor.execute("SELECT id FROM clientes WHERE nombre = ? OR apodo = ? LIMIT 1", (cliente, empresa))
        res_cli = cursor.fetchone()
        if res_cli:
            cliente_id = res_cli[0]
        else:
            cursor.execute("INSERT INTO clientes (nombre, apodo, sincronizado) VALUES (?, ?, 0)", (cliente, empresa))
            if hasattr(cursor, "lastrowid") and cursor.lastrowid:
                cliente_id = cursor.lastrowid
            else:
                cursor.execute("SELECT MAX(id) FROM clientes")
                cliente_id = cursor.fetchone()[0]
            
        monto_total = monto_soft + (monto_memb * meses_memb)
        
        cursor.execute("""
            INSERT INTO ordenes (negocio_id, cliente_id, descripcion, monto_total, costo_insumos, fecha_ingreso, estado, sincronizado)
            VALUES (2, ?, ?, ?, 0, ?, 'Venta', 0)
        """, (cliente_id, desc.upper(), monto_total, fecha_manual.strftime("%Y-%m-%d")))
        
        if hasattr(cursor, "lastrowid") and cursor.lastrowid:
            orden_id = cursor.lastrowid
        else:
            cursor.execute("SELECT MAX(id) FROM ordenes")
            orden_id = cursor.fetchone()[0]
        
        # Generar pagos de software
        if monto_soft > 0:
            val_cuota_soft = monto_soft / cuotas_soft
            for i in range(1, cuotas_soft + 1):
                vence = fecha_manual + relativedelta(months=i-1)
                cursor.execute("""
                    INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas, sincronizado)
                    VALUES (?, ?, ?, 'Pendiente', ?, 0)
                """, (orden_id, val_cuota_soft, vence.strftime("%Y-%m-%d"), f"SOFTWARE CUOTA {i}/{cuotas_soft}"))
                
        # Generar pagos de membresía
        if monto_memb > 0:
            for i in range(1, meses_memb + 1):
                vence_m = fecha_manual + relativedelta(months=i-1)
                cursor.execute("""
                    INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas, sincronizado)
                    VALUES (?, ?, ?, 'Pendiente', ?, 0)
                """, (orden_id, monto_memb, vence_m.strftime("%Y-%m-%d"), f"MEMBRESÍA MES {i}/{meses_memb}"))
                
        conn.commit()

def render(get_connection):
    st.title("Cargar Nueva Operación")

    negocio_nom = st.radio(
        "Facturar con:", ["GHV - Service", "OnXpert Software"], horizontal=True
    )
    n_id = 1 if negocio_nom == "GHV - Service" else 2

    try:
        with get_connection() as conn:
            df_c = pd.read_sql_query(
                "SELECT id, apodo || ' - ' || nombre as cliente_display FROM clientes WHERE activo = 1",
                conn,
            )
    except Exception as e:
        st.error(f"Error al cargar clientes: {e}")
        df_c = pd.DataFrame()

    if not df_c.empty:
        cliente_dict = dict(zip(df_c["cliente_display"], df_c["id"]))
        c_sel = st.selectbox(
            "Seleccionar Cliente:", options=list(cliente_dict.keys())
        )

        tipo_op = st.selectbox("¿Qué vas a registrar?", [
            "🛒 Venta de Artículo (Hardware)",
            "🛠️ Servicio Técnico (GHV)",
            "💻 Software / Membresía (OnXpert)",
        ])

        if tipo_op == "🛒 Venta de Artículo (Hardware)":
            tipo_v = st.radio("Condición", ["Contado", "Cuotas"], horizontal=True)
            cant_c = (
                st.number_input(
                    "Cantidad de Cuotas", min_value=2, max_value=36, value=2
                )
                if tipo_v == "Cuotas"
                else 1
            )

            st.markdown("---")
            modo_inv_v = st.checkbox(
                "🔍 Seleccionar producto desde Inventario registrado", value=False
            )

            prod_inv_id = None
            precio_sug_v = 0
            costo_sug_v = 0
            desc_sug_v = ""

            if modo_inv_v:
                try:
                    with get_connection() as conn_inv:
                        df_prod_v = pd.read_sql_query(
                            """
                                SELECT id, categoria || ' ' || marca || ' (' || capacidad_especificacion || ') - Stock: ' || stock as display, 
                                       precio_venta, precio_costo, stock, categoria || ' ' || marca || ' (' || capacidad_especificacion || ')' as nombre_corto
                                FROM productos WHERE stock > 0
                            """,
                            conn_inv,
                        )
                except Exception:
                    df_prod_v = pd.DataFrame()

                if not df_prod_v.empty:
                    p_v_sel_display = st.selectbox(
                        "Buscar Producto en Stock:", df_prod_v["display"]
                    )
                    match_v = df_prod_v[
                        df_prod_v["display"] == p_v_sel_display
                    ].iloc[0]
                    precio_sug_v = int(match_v["precio_venta"])
                    costo_sug_v = int(match_v["precio_costo"])
                    desc_sug_v = str(match_v["nombre_corto"])
                    prod_inv_id = int(match_v["id"])
                else:
                    st.info(
                        "No hay productos disponibles en el Inventario con Stock mayor a 0."
                    )

            c1, c2 = st.columns(2)
            with c1:
                monto_v = st.number_input(
                    "Precio Venta (Gs)",
                    min_value=0,
                    step=50000,
                    value=precio_sug_v,
                    format="%d",
                )
                entrega = st.number_input(
                    "Entrega Inicial (Gs)", min_value=0, step=50000, format="%d"
                )
                if entrega > 0:
                    st.info(f"Entrega: **{int(entrega):,} Gs.**".replace(",", "."))

            with c2:
                costo_h = st.number_input(
                    "Costo Compra (Gs)",
                    min_value=0,
                    step=50000,
                    value=costo_sug_v,
                    format="%d",
                )
                f_v = st.date_input("Fecha", value=datetime.now().date())

            ganancia_v = monto_v - costo_h
            margen_v = (ganancia_v / monto_v * 100) if monto_v > 0 else 0.0

            mc1, mc2, mc3 = st.columns(3)
            mc1.info(f"**Monto:** {int(monto_v):,} Gs.".replace(",", "."))
            mc2.warning(f"**Costo:** {int(costo_h):,} Gs.".replace(",", "."))
            if ganancia_v >= 0:
                mc3.success(
                    f"**Ganancia:** {int(ganancia_v):,} Gs. ({margen_v:.1f}%)".replace(
                        ",", "."
                    )
                )
            else:
                mc3.error(
                    f"**Pérdida:** {int(ganancia_v):,} Gs. ({margen_v:.1f}%)".replace(
                        ",", "."
                    )
                )

            descontar_stock_v = False
            if modo_inv_v and prod_inv_id:
                descontar_stock_v = st.checkbox(
                    "📦 Descontar 1 unidad del Stock en Inventario", value=True
                )

            with st.form("form_hardware_detalles", clear_on_submit=True):
                prod = st.text_input("Producto / Descripción", value=desc_sug_v)
                enviar = st.form_submit_button("Confirmar Venta")

            if enviar:
                if not prod:
                    st.error("⚠️ Por favor ingresa una descripción para el producto.")
                else:
                    try:
                        with get_connection() as conn_op:
                            cursor_op = conn_op.cursor()
                            cursor_op.execute(
                                """
                                    INSERT INTO ordenes (negocio_id, cliente_id, descripcion, monto_total, costo_insumos, fecha_ingreso, estado, sincronizado)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                                """,
                                (
                                    n_id,
                                    cliente_dict[c_sel],
                                    prod.upper(),
                                    monto_v,
                                    costo_h,
                                    f_v.strftime("%Y-%m-%d"),
                                    "Venta",
                                ),
                            )

                            if hasattr(cursor_op, "lastrowid") and cursor_op.lastrowid:
                                orden_id = cursor_op.lastrowid
                            else:
                                cursor_op.execute("SELECT MAX(id) FROM ordenes")
                                orden_id = cursor_op.fetchone()[0]

                            if modo_inv_v and prod_inv_id and descontar_stock_v:
                                cursor_op.execute(
                                    "UPDATE productos SET stock = stock - 1, sincronizado = 0 WHERE id = ?",
                                    (prod_inv_id,),
                                )

                            if entrega > 0:
                                cursor_op.execute(
                                    """
                                        INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas, sincronizado)
                                        VALUES (?, ?, ?, 'Pagado', 'ENTREGA INICIAL', 0)
                                    """,
                                    (orden_id, entrega, f_v.strftime("%Y-%m-%d")),
                                )

                            saldo = monto_v - entrega
                            if saldo > 0:
                                if tipo_v == "Contado":
                                    cursor_op.execute(
                                        """
                                            INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas, sincronizado)
                                            VALUES (?, ?, ?, 'Pendiente', 'SALDO CONTADO', 0)
                                        """,
                                        (orden_id, saldo, f_v.strftime("%Y-%m-%d")),
                                    )
                                else:
                                    n_cuotas = cant_c
                                    por_cuota = saldo / n_cuotas
                                    for i in range(1, n_cuotas + 1):
                                        vence_c = f_v + relativedelta(months=i)
                                        cursor_op.execute(
                                            """
                                                INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas, sincronizado)
                                                VALUES (?, ?, ?, 'Pendiente', ?, 0)
                                            """,
                                            (
                                                orden_id,
                                                por_cuota,
                                                vence_c.strftime("%Y-%m-%d"),
                                                f"CUOTA {i}/{n_cuotas}",
                                            ),
                                        )

                            conn_op.commit()
                            st.success("✅ ¡Venta registrada exitosamente!")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

        elif tipo_op == "🛠️ Servicio Técnico (GHV)":
            eq = st.text_input("Equipo (Ej: Notebook ASUS X515)", key="svc_eq")
            fa = st.text_input(
                "Falla reportada (Ej: Lentitud extrema / Mantenimiento)", key="svc_fa"
            )

            c1, c2 = st.columns(2)
            with c1:
                monto_cliente_mo = st.number_input(
                    "Precio Trabajo / Mano de Obra al Cliente (Gs)",
                    min_value=0,
                    step=10000,
                    value=0,
                    key="svc_mo",
                )
                costo_tercerizado = st.number_input(
                    "Costo Tercerizado - Lo que pagás afuera (Gs)",
                    min_value=0,
                    step=10000,
                    value=0,
                    key="svc_terc",
                )

                mano_de_obra_pura = max(0, monto_cliente_mo - costo_tercerizado)
                st.caption(
                    f"💡 **Ganancia Pura GHV (Calculada):**"
                    f" {int(mano_de_obra_pura):,} Gs.".replace(",", ".")
                )

            with c2:
                entrega_svc = st.number_input(
                    "Entrega Inicial del Cliente (Gs)",
                    min_value=0,
                    step=50000,
                    key="svc_ent",
                )
                cant_c = st.number_input(
                    "Cuotas del Saldo Restante", min_value=1, value=1, key="svc_cuotas"
                )
                f_v = st.date_input(
                    "Fecha Temprana", value=datetime.now().date(), key="svc_fecha"
                )

            st.markdown("---")
            st.markdown("#### ➕ Agregar Insumos / Repuestos desde Stock")

            try:
                with get_connection() as conn_prod:
                    df_prod_disponibles = pd.read_sql_query(
                        """
                            SELECT id, categoria || ' ' || marca || ' (' || capacidad_especificacion || ') - Stock: ' || stock as display, 
                                   precio_venta, precio_costo, stock, categoria || ' ' || marca || ' (' || capacidad_especificacion || ')' as nombre_corto
                            FROM productos WHERE stock > 0
                        """,
                        conn_prod,
                    )
            except Exception:
                df_prod_disponibles = pd.DataFrame()

            if "insumos_orden" not in st.session_state:
                st.session_state.insumos_orden = []

            if df_prod_disponibles.empty:
                st.info(
                    "No hay productos cargados en el Inventario o no queda stock disponible."
                )
            else:
                col_sel_p, col_cant_p, col_btn_p = st.columns([3, 1, 1])
                p_elegido_display = col_sel_p.selectbox(
                    "Seleccionar Repuesto:",
                    df_prod_disponibles["display"],
                    key="p_insumo_sel",
                )
                cant_elegida = col_cant_p.number_input(
                    "Cantidad", min_value=1, value=1, key="p_insumo_cant"
                )

                if col_btn_p.button("➕ Añadir Insumo", use_container_width=True):
                    match_p = df_prod_disponibles[
                        df_prod_disponibles["display"] == p_elegido_display
                    ].iloc[0]
                    if cant_elegida > match_p["stock"]:
                        st.error(
                            f"No podés agregar {cant_elegida} unidades. Solo quedan {match_p['stock']} en stock."
                        )
                    else:
                        st.session_state.insumos_orden.append({
                            "id": int(match_p["id"]),
                            "nombre": match_p["nombre_corto"],
                            "cantidad": int(cant_elegida),
                            "precio_venta": float(match_p["precio_venta"]),
                            "precio_costo": float(match_p["precio_costo"]),
                        })
                        st.toast("Insumo agregado a la lista temporal.")

            total_insumos_venta = 0.0
            total_insumos_costo = 0.0
            detalle_insumos_texto = ""

            if st.session_state.insumos_orden:
                st.markdown("##### 📋 Lista de Insumos para esta OT")
                for idx, ins in enumerate(st.session_state.insumos_orden):
                    subtotal_i = ins["cantidad"] * ins["precio_venta"]
                    total_insumos_venta += subtotal_i
                    total_insumos_costo += ins["cantidad"] * ins["precio_costo"]
                    detalle_insumos_texto += f"\n- {ins['cantidad']}x {ins['nombre']}"

                    c_i1, c_i2, c_i3 = st.columns([3, 1, 1])
                    c_i1.markdown(f"🔹 **{ins['nombre']}** (Cant: {ins['cantidad']})")
                    c_i2.markdown(f"{int(subtotal_i):,} Gs.".replace(",", "."))
                    if c_i3.button("🗑️", key=f"del_ins_{idx}"):
                        st.session_state.insumos_orden.pop(idx)
                        st.rerun()

            precio_final_calculado = monto_cliente_mo + total_insumos_venta
            total_costos_calculado = total_insumos_costo + costo_tercerizado
            ganancia_estimada = precio_final_calculado - total_costos_calculado

            st.markdown("---")
            st.markdown(
                "### 🧮 Total Proyectado al Cliente:"
                f" **{int(precio_final_calculado):,} Gs.**".replace(",", ".")
            )
            st.caption(
                f"Trabajo/Servicio: {int(monto_cliente_mo):,} Gs.".replace(",", ".")
                + " | Repuestos:"
                f" {int(total_insumos_venta):,} Gs.".replace(",", ".")
            )
            st.info(
                f"💡 **Costo Real Total:** {int(total_costos_calculado):,}"
                " Gs. | **Ganancia Neta Estimada:**"
                f" {int(ganancia_estimada):,} Gs.".replace(",", ".")
            )

            col_sub1, col_sub2 = st.columns(2)
            with col_sub1:
                enviar_svc = st.button(
                    "🚀 Registrar Servicio Técnico Completo", use_container_width=True
                )
            with col_sub2:
                if st.button("❌ Limpiar Todo", use_container_width=True):
                    st.session_state.insumos_orden = []
                    st.rerun()

            if enviar_svc:
                if not eq or not fa:
                    st.error("⚠️ Por favor, completa el equipo y la falla.")
                else:
                    try:
                        with get_connection() as conn_op:
                            cursor_op = conn_op.cursor()
                            id_cliente_actual = cliente_dict[c_sel]

                            descripcion_completa_ot = f"{eq.upper()} - FALLA: {fa.upper()}"
                            if costo_tercerizado > 0:
                                descripcion_completa_ot += (
                                    "\n\n⚙️ TRABAJO TERCERIZADO INCLUIDO (Costo:"
                                    f" {int(costo_tercerizado):,} Gs.)".replace(",", ".")
                                )
                            if detalle_insumos_texto:
                                descripcion_completa_ot += (
                                    f"\n\n🛠️ COMPONENTES INSTALADOS:{detalle_insumos_texto.upper()}"
                                )

                            cursor_op.execute(
                                """
                                    INSERT INTO ordenes (negocio_id, cliente_id, descripcion, fecha_ingreso, monto_total, costo_insumos, estado, sincronizado)
                                    VALUES (1, ?, ?, ?, ?, ?, 'En Proceso', 0)
                                """,
                                (
                                    id_cliente_actual,
                                    descripcion_completa_ot,
                                    f_v.strftime("%Y-%m-%d"),
                                    precio_final_calculado,
                                    total_costos_calculado,
                                ),
                            )

                            if hasattr(cursor_op, "lastrowid") and cursor_op.lastrowid:
                                orden_id = cursor_op.lastrowid
                            else:
                                cursor_op.execute("SELECT MAX(id) FROM ordenes")
                                orden_id = cursor_op.fetchone()[0]

                            for ins in st.session_state.insumos_orden:
                                cursor_op.execute(
                                    """
                                        UPDATE productos 
                                        SET stock = stock - ?, sincronizado = 0 
                                        WHERE id = ?
                                    """,
                                    (ins["cantidad"], ins["id"]),
                                )

                            if entrega_svc > 0:
                                cursor_op.execute(
                                    """
                                        INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas, sincronizado)
                                        VALUES (?, ?, ?, 'Pagado', 'ENTREGA INICIAL', 0)
                                    """,
                                    (orden_id, entrega_svc, f_v.strftime("%Y-%m-%d")),
                                )

                            saldo_restante = precio_final_calculado - entrega_svc
                            if saldo_restante > 0:
                                if int(cant_c) == 1:
                                    cursor_op.execute(
                                        """
                                            INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas, sincronizado)
                                            VALUES (?, ?, ?, 'Pendiente', 'SALDO CONTADO', 0)
                                        """,
                                        (orden_id, saldo_restante, f_v.strftime("%Y-%m-%d")),
                                    )
                                else:
                                    monto_c = saldo_restante / int(cant_c)
                                    for i in range(1, int(cant_c) + 1):
                                        vencimiento = f_v + relativedelta(months=i)
                                        cursor_op.execute(
                                            """
                                                INSERT INTO pagos (orden_id, monto_cuota, fecha_vencimiento, estado, notas, sincronizado)
                                                VALUES (?, ?, ?, 'Pendiente', ?, 0)
                                            """,
                                            (
                                                orden_id,
                                                monto_c,
                                                vencimiento.strftime("%Y-%m-%d"),
                                                f"CUOTA {i}/{int(cant_c)}",
                                            ),
                                        )

                            conn_op.commit()

                            st.session_state.insumos_orden = []
                            st.success(
                                "✅ ¡Servicio Técnico Registrado con éxito! OT"
                                f" #{orden_id} generada y Stock actualizado."
                            )
                            time.sleep(1)
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error al registrar: {e}")

        elif tipo_op == "💻 Software / Membresía (OnXpert)":
            soft = st.text_input(
                "Nombre / Descripción del Sistema",
                placeholder="Ej: Sistema de Automatización y Marcación",
            )

            c1, c2 = st.columns(2)
            with c1:
                ms = st.number_input(
                    "Costo Software / Implementación (Gs)",
                    min_value=0,
                    step=100000,
                    value=0,
                    format="%d",
                )
                cuotas_soft = st.number_input(
                    "Pagos para el Software (1 = Pago único)",
                    min_value=1,
                    max_value=12,
                    value=1,
                )
                if ms > 0:
                    val_c_soft = ms / cuotas_soft
                    st.caption(
                        f"💡 Software: {cuotas_soft} pago(s) de"
                        f" **{int(val_c_soft):,} Gs.**".replace(",", ".")
                    )

            with c2:
                mm = st.number_input(
                    "Membresía Mensual / Mantenimiento (Gs)",
                    min_value=0,
                    step=50000,
                    value=0,
                    format="%d",
                )
                meses_memb = st.number_input(
                    "Cantidad de meses de Membresía",
                    min_value=1,
                    max_value=36,
                    value=12,
                )
                if mm > 0:
                    st.caption(
                        f"💡 Membresía: {meses_memb} mes(es) de"
                        f" **{int(mm):,} Gs.**".replace(",", ".")
                    )

            f_v = st.date_input(
                "Fecha de Inicio / Contrato", value=datetime.now().date()
            )

            monto_total_contrato = ms + (mm * meses_memb)
            st.info(
                "💰 **Monto Total del Contrato:**"
                f" {int(monto_total_contrato):,} Gs.".replace(",", ".")
            )

            if st.button(
                "🚀 Registrar Software y Membresía", use_container_width=True
            ):
                if not soft:
                    st.error("⚠️ Por favor ingresa el nombre o descripción del sistema.")
                else:
                    partes = c_sel.split(" - ")
                    empresa_p = partes[0] if len(partes) > 0 else ""
                    nombre_p = partes[1] if len(partes) > 1 else c_sel

                    try:
                        registrar_venta_onxpert(
                            get_connection=get_connection,
                            cliente=nombre_p,
                            empresa=empresa_p,
                            telefono="",
                            desc=soft.upper(),
                            monto_soft=ms,
                            cuotas_soft=int(cuotas_soft),
                            monto_memb=mm,
                            meses_memb=int(meses_memb),
                            fecha_manual=f_v,
                        )
                        st.success(
                            "✅ Operación de Software/Membresía registrada correctamente."
                        )
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al registrar software: {e}")
    else:
        st.warning("Primero debés dar de alta un cliente en 'Gestión de Clientes'.")