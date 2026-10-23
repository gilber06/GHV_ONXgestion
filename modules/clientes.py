import streamlit as pd
import streamlit as st
import pandas as pd

def render(get_connection):
    st.title("Gestión Centralizada de Clientes")

    def actualizar_datos_cliente(cli_id, nombre, empresa, telefono, ruc):
        with get_connection() as c:
            c.execute(
                """
                UPDATE clientes 
                SET nombre = ?, apodo = ?, telefono = ?, ruc_ci = ?, sincronizado = 0 
                WHERE id = ?
                """,
                (nombre.strip().upper(), empresa.strip().upper(), telefono.strip(), ruc.strip().upper(), cli_id)
            )
            c.commit()

    def cambiar_estado_cliente(cli_id, activo=False):
        val_activo = 1 if activo else 0
        with get_connection() as c:
            c.execute(
                "UPDATE clientes SET activo = ?, sincronizado = 0 WHERE id = ?",
                (val_activo, cli_id)
            )
            c.commit()

    tab1, tab2, tab3 = st.tabs(
        ["➕ Registrar Nuevo", "📝 Ver / Editar", "🚫 Dar de Baja"]
    )

    with tab1:
        st.subheader("Cargar Cliente al Sistema")
        with st.form("nuevo_cliente_unificado", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre y Apellido / Razón Social")
                empresa = st.text_input("Empresa / Apodo (Ej: La Hornalla)")
            with col2:
                telefono = st.text_input("Teléfono / WhatsApp")
                ruc = st.text_input("RUC o CI")

            boton_guardar = st.form_submit_button("Dar de Alta Cliente")

        if boton_guardar:
            if not nombre:
                st.error("⚠️ El campo 'Nombre y Apellido / Razón Social' es obligatorio.")
            else:
                nombre_norm = nombre.strip().upper()
                empresa_norm = empresa.strip().upper() if empresa else ""
                ruc_norm = ruc.strip().upper() if ruc else ""

                with get_connection() as conn_local:
                    cursor_local = conn_local.cursor()
                    cursor_local.execute(
                        "SELECT id FROM clientes WHERE UPPER(nombre) = ? AND activo = 1",
                        (nombre_norm,),
                    )
                    existe_nombre = cursor_local.fetchone()

                    existe_ruc = None
                    if ruc_norm:
                        cursor_local.execute(
                            "SELECT nombre FROM clientes WHERE ruc_ci = ? AND activo = 1",
                            (ruc_norm,),
                        )
                        existe_ruc = cursor_local.fetchone()

                    if existe_nombre:
                        st.warning(f"⚠️ El cliente '{nombre_norm}' ya existe.")
                    else:
                        if existe_ruc:
                            st.info(
                                f"ℹ️ Nota: El RUC {ruc_norm} ya está asociado a"
                                f" '{existe_ruc[0]}'."
                            )

                        try:
                            cursor_local.execute(
                                """
                                INSERT INTO clientes (nombre, apodo, telefono, ruc_ci, activo, sincronizado)
                                VALUES (?, ?, ?, ?, 1, 0)
                            """,
                                (nombre_norm, empresa_norm, telefono.strip(), ruc_norm),
                            )
                            conn_local.commit()
                            st.success(
                                f"✅ ¡Registro exitoso! '{nombre_norm}' guardado"
                                " correctamente."
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar: {e}")

    with tab2:
        st.subheader("Base de Datos Actual")
        with get_connection() as conn:
            df_clientes = pd.read_sql_query(
                "SELECT id, nombre, apodo as Empresa, telefono, ruc_ci FROM clientes"
                " WHERE activo = 1 AND nombre != 'ELIMINAR'",
                conn,
            )

        busqueda = st.text_input("🔍 Buscar cliente por nombre o empresa:", "")
        if busqueda:
            df_clientes = df_clientes[
                df_clientes["nombre"].str.contains(busqueda, case=False, na=False)
                | df_clientes["Empresa"].str.contains(busqueda, case=False, na=False)
            ]
        df_clientes = df_clientes.drop_duplicates(subset=["id"]).reset_index(
            drop=True
        )
        st.dataframe(df_clientes, width="stretch")

        st.markdown("---")
        st.subheader("📝 Editar Datos de Cliente")

        with get_connection() as conn:
            clientes_edicion = pd.read_sql_query(
                "SELECT id, nombre, apodo, telefono, ruc_ci FROM clientes WHERE activo"
                " = 1 GROUP BY id, nombre",
                conn,
            )

        if not clientes_edicion.empty:
            opciones_cliente = {}
            for _, row in clientes_edicion.iterrows():
                clave = f"{row['id']} - {row['nombre']}"
                opciones_cliente[clave] = {
                    "id": row["id"],
                    "nombre": row["nombre"],
                    "apodo": row["apodo"],
                    "telefono": row["telefono"],
                    "ruc_ci": row["ruc_ci"],
                }

            seleccion = st.selectbox(
                "Seleccione el cliente para modificar:",
                options=list(opciones_cliente.keys()),
            )
            datos_actuales = opciones_cliente[seleccion]

            val_nom = (
                str(datos_actuales["nombre"])
                if pd.notna(datos_actuales["nombre"])
                else ""
            )
            val_apo = (
                str(datos_actuales["apodo"])
                if pd.notna(datos_actuales["apodo"])
                else ""
            )
            val_tel = (
                str(datos_actuales["telefono"])
                if pd.notna(datos_actuales["telefono"])
                else ""
            )
            val_ruc = (
                str(datos_actuales["ruc_ci"])
                if pd.notna(datos_actuales["ruc_ci"])
                else ""
            )

            with st.form("form_edicion_cliente"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    n_nombre = st.text_input("Nombre Completo:", value=val_nom)
                    n_empresa = st.text_input("Empresa / Apodo:", value=val_apo)
                with col_e2:
                    n_telefono = st.text_input("Teléfono:", value=val_tel)
                    n_ruc = st.text_input("RUC / CI:", value=val_ruc)

                if st.form_submit_button("Guardar Cambios"):
                    actualizar_datos_cliente(
                        datos_actuales["id"], n_nombre, n_empresa, n_telefono, n_ruc
                    )
                    st.success("¡Datos actualizados!")
                    st.rerun()
        else:
            st.info("No hay clientes registrados.")

    with tab3:
        st.subheader("Desactivar Cliente")
        st.warning(
            "Esto ocultará al cliente de las listas de ventas, pero no borrará sus"
            " registros históricos."
        )

        with get_connection() as conn:
            df_bajas = pd.read_sql_query(
                "SELECT id, nombre, apodo FROM clientes WHERE activo = 1", conn
            )

        if not df_bajas.empty:
            opciones_baja = {
                f"{row['id']} - {row['nombre']} ({row['apodo']})": row["id"]
                for _, row in df_bajas.iterrows()
            }
            cliente_a_eliminar = st.selectbox(
                "Seleccione el cliente a desactivar:",
                options=list(opciones_baja.keys()),
            )
            id_para_baja = opciones_baja[cliente_a_eliminar]

            if st.button("Confirmar Baja Definitiva"):
                cambiar_estado_cliente(id_para_baja, activo=False)
                st.error(f"Cliente con ID {id_para_baja} ha sido desactivado.")
                st.rerun()
        else:
            st.info("No hay clientes activos para dar de baja.")