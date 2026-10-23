import streamlit as st
import os

def render(get_connection):
    with st.sidebar.expander("🛠️ Herramientas de Mantenimiento"):
        
        st.subheader("Borrar Pagos Erróneos")
        ids_a_borrar = st.text_input("IDs a eliminar:", value="")
        if st.button("🗑️ Ejecutar Eliminación"):
            try:
                ids_list = [int(x.strip()) for x in ids_a_borrar.split(",") if x.strip()]
                if ids_list:
                    with get_connection() as conn:
                        placeholders = ",".join(["?"] * len(ids_list))
                        conn.execute(f"DELETE FROM pagos WHERE id IN ({placeholders})", ids_list)
                        conn.commit()
                    st.success(f"¡Registros {ids_list} eliminados con éxito!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("---")
        st.subheader("Ver Tablas de la BD")
        if st.button("🔍 Mostrar tablas"):
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tablas = cursor.fetchall()
                st.success(f"Tablas encontradas: {tablas}")
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("---")
        st.subheader("Reparaciones Rápidas")
        id_nota_str = st.text_input("ID a reparar:", value="")
        nueva_nota = st.text_input("Texto de la nota:", value="")
        if st.button("📝 Actualizar Nota"):
            try:
                if not id_nota_str.strip():
                    st.warning("Por favor ingresa un ID.")
                else:
                    id_nota = int(id_nota_str.strip())
                    with get_connection() as conn:
                        conn.execute("UPDATE pagos SET notas = ? WHERE id = ?", (nueva_nota, id_nota))
                        conn.commit()
                    st.success(f"¡Nota del ID {id_nota} actualizada con éxito!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    turso_url_check = None
    try:
        if hasattr(st, "secrets") and "TURSO_DATABASE_URL" in st.secrets:
            turso_url_check = st.secrets["TURSO_DATABASE_URL"]
    except Exception:
        pass

    if turso_url_check:
        st.sidebar.success("🟢 La web ESTÁ conectada a Turso (Nube)")
    else:
        st.sidebar.error("🔴 La web ESTÁ usando SQLite local (Archivo viejo)")