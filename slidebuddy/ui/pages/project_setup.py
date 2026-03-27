import streamlit as st
from slidebuddy.config.defaults import DB_PATH, UPLOADS_DIR, LANGUAGES, TEXT_LENGTHS, load_preferences
from slidebuddy.db.migrations import get_connection
from slidebuddy.db.queries import (
    create_project, delete_project, get_project, get_all_projects,
    get_sources_for_project, create_source, update_source_status, delete_source,
)
from slidebuddy.db.models import Project, Source
from slidebuddy.parsers import parse_source, get_source_type, SUPPORTED_EXTENSIONS
from slidebuddy.rag.chunking import chunk_text
from slidebuddy.rag.retrieval import add_source_chunks
from slidebuddy.ui.components.stepbar import render_stepbar
from pathlib import Path
import json


def _delete_project_full(conn, project_id: str):
    """Delete a project including its RAG data and uploaded files."""
    try:
        from slidebuddy.rag.chroma_manager import delete_project_sources_collection
        delete_project_sources_collection(project_id)
    except Exception:
        pass  # Collection already deleted or client unavailable

    upload_dir = UPLOADS_DIR / project_id
    if upload_dir.exists():
        import shutil
        shutil.rmtree(upload_dir, ignore_errors=True)

    # Delete from DB (cascades to sources, chapters, slides, versions, source_gaps)
    delete_project(conn, project_id)


def render_project_setup():
    st.header("Projekte")

    project_id = st.session_state.get("current_project_id")

    if project_id:
        _render_project_detail(project_id)
    else:
        _render_project_list()


def _invalidate_caches():
    """Clear sidebar caches after data changes."""
    from slidebuddy.ui.sidebar import _load_projects
    _load_projects.clear()


def _render_project_list():
    st.subheader("Neues Projekt erstellen")

    with st.form("new_project"):
        name = st.text_input("Projektname")
        topic = st.text_area("Thema / Beschreibung")
        col1, col2 = st.columns(2)
        with col1:
            language = st.selectbox("Sprache", LANGUAGES, format_func=lambda x: "Deutsch" if x == "de" else "English")
        with col2:
            text_length = st.selectbox("Textumfang", TEXT_LENGTHS, index=1)

        submitted = st.form_submit_button("Projekt erstellen")

        if submitted and name:
            conn = get_connection(DB_PATH)
            project = Project(name=name, topic=topic, language=language, global_text_length=text_length)
            create_project(conn, project)
            conn.close()
            st.session_state.current_project_id = project.id
            _invalidate_caches()
            st.rerun()

    st.divider()
    st.subheader("Vorhandene Projekte")

    conn = get_connection(DB_PATH)
    projects = get_all_projects(conn)
    conn.close()

    if not projects:
        st.info("Noch keine Projekte vorhanden. Erstelle dein erstes Projekt oben.")
    else:
        for project in projects:
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    st.markdown(f"**{project.name}**")
                    if project.topic:
                        st.caption(project.topic[:100])
                with col2:
                    st.caption(f"🌐 {project.language.upper()}")
                with col3:
                    if st.button("Öffnen", key=f"open_{project.id}"):
                        st.session_state.current_project_id = project.id
                        st.rerun()
                with col4:
                    confirm_key = f"_confirm_del_{project.id}"
                    if st.session_state.get(confirm_key):
                        if st.button("Wirklich?", key=f"del_yes_{project.id}", type="primary"):
                            conn2 = get_connection(DB_PATH)
                            _delete_project_full(conn2, project.id)
                            conn2.close()
                            st.session_state.pop(confirm_key, None)
                            _invalidate_caches()
                            st.rerun()
                    else:
                        if st.button("🗑️", key=f"del_{project.id}"):
                            st.session_state[confirm_key] = True
                            st.rerun()


def _render_project_detail(project_id: str):
    conn = get_connection(DB_PATH)
    project = get_project(conn, project_id)

    if not project:
        st.error("Projekt nicht gefunden.")
        conn.close()
        return

    # Header with back button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Zurück"):
            st.session_state.current_project_id = None
            st.rerun()
    with col2:
        st.subheader(project.name)

    render_stepbar(conn, project_id, "sources")

    if project.topic:
        st.caption(project.topic)

    st.divider()

    # Source upload section
    st.subheader("📎 Quellen hochladen")

    with st.form(f"upload_form_{project_id}", clear_on_submit=True):
        uploaded_files = st.file_uploader(
            "Dateien hochladen",
            accept_multiple_files=True,
            type=list(ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS.keys()),
            key=f"upload_{project_id}",
        )
        submit = st.form_submit_button("Hochladen & verarbeiten", type="primary", use_container_width=True)

    _MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

    if submit and uploaded_files:
        existing_sources = {s.filename for s in get_sources_for_project(conn, project_id)}
        for uploaded_file in uploaded_files:
            if uploaded_file.name in existing_sources:
                st.info(f"'{uploaded_file.name}' ist bereits vorhanden — übersprungen.")
                continue

            file_size = len(uploaded_file.getbuffer())
            if file_size > _MAX_UPLOAD_BYTES:
                st.error(f"'{uploaded_file.name}' ist zu gross ({file_size / 1024 / 1024:.0f} MB). Maximum: 50 MB.")
                continue

            file_path = UPLOADS_DIR / project_id / uploaded_file.name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(uploaded_file.getbuffer())

            source_type = get_source_type(file_path)
            if source_type:
                source = Source(
                    project_id=project_id,
                    source_type=source_type,
                    filename=uploaded_file.name,
                )
                create_source(conn, source)

                # Process source
                try:
                    update_source_status(conn, source.id, "processing")
                    text = parse_source(file_path)
                    rag_prefs = load_preferences().get("rag", {})
                    chunks = chunk_text(text, chunk_size=rag_prefs.get("chunk_size", 500), overlap=rag_prefs.get("chunk_overlap", 50))
                    add_source_chunks(
                        project_id, source.id, chunks,
                        {"source_type": source_type, "filename": uploaded_file.name},
                    )
                    update_source_status(conn, source.id, "done", chunk_count=len(chunks))
                    source.original_text = text
                    conn.execute(
                        "UPDATE sources SET original_text = ? WHERE id = ?",
                        (text, source.id),
                    )
                    conn.commit()
                    st.success(f"✅ {uploaded_file.name} verarbeitet ({len(chunks)} Chunks)")
                except Exception as e:
                    update_source_status(conn, source.id, "error", error_message=str(e))
                    st.error(f"❌ Fehler bei {uploaded_file.name}: {e}")

    # YouTube URL input
    st.subheader("🎥 YouTube-Untertitel")
    youtube_url = st.text_input("YouTube-URL", key=f"yt_{project_id}")
    if st.button("Untertitel abrufen", key=f"yt_btn_{project_id}") and youtube_url:
        from slidebuddy.parsers.youtube_parser import parse_youtube, get_youtube_metadata
        with st.spinner("Untertitel werden abgerufen..."):
            meta = get_youtube_metadata(youtube_url)
            display_name = f"{meta['title']} — {meta['uploader']}"
            transcript = parse_youtube(youtube_url, project.language)
            if transcript:
                source = Source(
                    project_id=project_id,
                    source_type="youtube",
                    filename=display_name,
                    original_text=transcript,
                )
                create_source(conn, source)
                rag_prefs = load_preferences().get("rag", {})
                chunks = chunk_text(transcript, chunk_size=rag_prefs.get("chunk_size", 500), overlap=rag_prefs.get("chunk_overlap", 50))
                add_source_chunks(
                    project_id, source.id, chunks,
                    {"source_type": "youtube", "filename": display_name},
                )
                update_source_status(conn, source.id, "done", chunk_count=len(chunks))
                st.success(f"✅ {display_name} — verarbeitet ({len(chunks)} Chunks)")
            else:
                st.warning("Keine Untertitel verfügbar. Bitte Transkript manuell hochladen.")

    # Show existing sources
    st.divider()
    st.subheader("Vorhandene Quellen")
    sources = get_sources_for_project(conn, project_id)

    if not sources:
        st.info("Noch keine Quellen hochgeladen.")
    else:
        for source in sources:
            status_icon = {"pending": "⏳", "processing": "🔄", "done": "✅", "error": "❌"}.get(source.processing_status, "❓")
            col_info, col_del = st.columns([5, 1])
            with col_info:
                st.markdown(f"{status_icon} **{source.filename}** ({source.source_type}) — {source.chunk_count or 0} Chunks")
                if source.error_message:
                    st.error(source.error_message)
            with col_del:
                if st.button("🗑️", key=f"del_{source.id}"):
                    from slidebuddy.rag.retrieval import delete_source_chunks
                    delete_source_chunks(project_id, source.id)
                    delete_source(conn, source.id)
                    _invalidate_caches()
                    st.rerun()

    # Navigation to next phase
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if sources and any(s.processing_status == "done" for s in sources):
            if st.button("▶️ Kapitelplanung starten", type="primary", use_container_width=True):
                st.session_state.current_page = "chapter_planning"
                st.rerun()

    # Project deletion
    st.divider()
    with st.expander("Projekt loeschen"):
        st.warning("Das Projekt und alle zugehoerigen Daten werden unwiderruflich geloescht.")
        if st.button("Projekt endgueltig loeschen", type="primary", key="delete_project_detail"):
            _delete_project_full(conn, project_id)
            st.session_state.current_project_id = None
            _invalidate_caches()
            st.rerun()

    conn.close()
