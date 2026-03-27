import time

import streamlit as st
from slidebuddy.config.defaults import DB_PATH
from slidebuddy.core.progress import detect_project_step, get_page_for_step
from slidebuddy.db.migrations import get_connection
from slidebuddy.db.queries import get_all_projects


@st.cache_data(ttl=10)
def _load_projects():
    conn = get_connection(DB_PATH)
    projects = get_all_projects(conn)
    conn.close()
    return projects


def render_sidebar():
    t0 = time.perf_counter()
    with st.sidebar:
        st.title("📊 SlideBuddy")
        st.caption("PowerPoint Content Agent")

        st.divider()

        # Navigation
        if st.button("🏠 Projekte", use_container_width=True):
            st.session_state.current_page = "projects"
            st.rerun()

        if st.button("⚙️ Einstellungen", use_container_width=True):
            st.session_state.current_page = "settings"
            st.rerun()

        if st.button("🔍 Chunk-Browser", use_container_width=True):
            st.session_state.current_page = "chunk_debug"
            st.rerun()

        if st.button("📐 Folienmaster", use_container_width=True):
            st.session_state.current_page = "slide_masters"
            st.rerun()

        st.divider()

        # Project list
        st.caption("PROJEKTE")
        try:
            projects = _load_projects()

            if not projects:
                st.caption("Noch keine Projekte vorhanden.")
            else:
                for project in projects:
                    if st.button(
                        f"📁 {project.name}",
                        key=f"proj_{project.id}",
                        use_container_width=True,
                    ):
                        st.session_state.current_project_id = project.id
                        conn = get_connection(DB_PATH)
                        step = detect_project_step(conn, project.id)
                        conn.close()
                        st.session_state.current_page = get_page_for_step(step)
                        st.rerun()
        except Exception:
            st.caption("Datenbank wird initialisiert...")

        st.divider()

    print(f"PERF sidebar: {int((time.perf_counter()-t0)*1000)}ms")
