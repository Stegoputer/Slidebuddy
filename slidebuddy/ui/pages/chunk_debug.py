import streamlit as st
from slidebuddy.config.defaults import DB_PATH
from slidebuddy.db.migrations import get_connection
from slidebuddy.db.queries import get_all_projects, get_sources_for_project
from slidebuddy.rag.chroma_manager import get_project_sources_collection


def render_chunk_debug():
    st.header("Chunk-Browser")

    conn = get_connection(DB_PATH)
    projects = get_all_projects(conn)

    if not projects:
        st.info("Noch keine Projekte vorhanden.")
        conn.close()
        return

    # Dropdown: Projekt
    project_names = {p.id: p.name for p in projects}
    selected_project_id = st.selectbox(
        "Projekt",
        options=[p.id for p in projects],
        format_func=lambda pid: project_names[pid],
        key="chunk_debug_project",
    )

    # Reset source/index when project changes
    if st.session_state.get("_chunk_debug_last_project") != selected_project_id:
        st.session_state["_chunk_debug_last_project"] = selected_project_id
        st.session_state.pop("chunk_debug_source", None)
        st.session_state.pop("chunk_idx", None)

    # Dropdown: Quelle
    sources = get_sources_for_project(conn, selected_project_id)
    conn.close()

    if not sources:
        st.info("Keine Quellen in diesem Projekt.")
        return

    source_labels = {s.id: f"{s.filename} ({s.chunk_count or 0} Chunks)" for s in sources}

    # No "Alle Quellen" option — always select a specific source
    source_options = [s.id for s in sources]

    # Reset slider when source changes
    def _on_source_change():
        st.session_state.pop("chunk_idx", None)

    selected_source_id = st.selectbox(
        "Quelle",
        options=source_options,
        format_func=lambda sid: source_labels.get(sid, sid),
        key="chunk_debug_source",
        on_change=_on_source_change,
    )

    # Load chunks from ChromaDB
    collection = get_project_sources_collection(selected_project_id)
    if collection.count() == 0:
        st.info("Keine Chunks in ChromaDB für dieses Projekt.")
        return

    result = collection.get(
        where={"source_id": selected_source_id},
        include=["documents", "metadatas"],
        limit=collection.count(),
    )

    if not result["documents"]:
        st.warning(f"Keine Chunks in ChromaDB für diese Quelle (source_id: `{selected_source_id[:12]}...`)")
        return

    # Sort by chunk_index
    paired = list(zip(result["documents"], result["metadatas"], result["ids"]))
    paired.sort(key=lambda x: x[1].get("chunk_index", 0))

    # Search filter
    search = st.text_input("Chunks durchsuchen", placeholder="Suchbegriff eingeben...", key="chunk_search")

    if search:
        search_lower = search.lower()
        paired = [(doc, meta, cid) for doc, meta, cid in paired if search_lower in doc.lower()]

    st.caption(f"{len(paired)} Chunks")

    # Chunk navigation
    if not paired:
        st.info("Keine Chunks entsprechen der Suche.")
        return

    max_idx = len(paired) - 1

    # Clamp index to valid range
    if "chunk_idx" not in st.session_state:
        st.session_state.chunk_idx = 0
    st.session_state.chunk_idx = min(st.session_state.chunk_idx, max_idx)
    chunk_idx = st.session_state.chunk_idx

    # Navigation: prev / label / next
    if max_idx > 0:
        col_prev, col_label, col_next = st.columns([1, 4, 1])
        with col_prev:
            st.button(
                "◀",
                use_container_width=True,
                key="chunk_prev",
                disabled=chunk_idx == 0,
                on_click=lambda: st.session_state.update(chunk_idx=chunk_idx - 1),
            )
        with col_label:
            st.markdown(
                f"<div style='text-align:center; padding:0.4rem 0; font-size:1.1rem;'>"
                f"Chunk <b>{chunk_idx + 1}</b> / {len(paired)}</div>",
                unsafe_allow_html=True,
            )
        with col_next:
            st.button(
                "▶",
                use_container_width=True,
                key="chunk_next",
                disabled=chunk_idx == max_idx,
                on_click=lambda: st.session_state.update(chunk_idx=chunk_idx + 1),
            )

    doc, meta, chunk_id = paired[chunk_idx]

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("**Metadaten**")
        st.json(meta)
    with col2:
        st.markdown(f"**ID:** `{chunk_id}`")
        st.markdown(f"**Zeichen:** {len(doc)} | **Tokens (ca.):** {len(doc) // 4}")

    st.text_area(
        "Chunk-Inhalt",
        value=doc,
        height=300,
        disabled=True,
        key=f"chunk_content_{selected_source_id}_{chunk_idx}",
    )
