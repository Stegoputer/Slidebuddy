"""Shared component: display RAG chunks used for generation + manual chunk search."""

import streamlit as st

from slidebuddy.rag.chroma_manager import get_project_sources_collection
from slidebuddy.rag.retrieval import search_project_sources


def render_rag_chunks(source_chunks: list[dict], label: str = "Verwendete Quellen-Chunks"):
    """Display RAG source chunks in an expander."""
    if not source_chunks:
        return
    with st.expander(f"📚 {label} ({len(source_chunks)})", expanded=False):
        for i, chunk in enumerate(source_chunks):
            meta = chunk.get("metadata", {})
            filename = meta.get("filename", "?")
            distance = chunk.get("distance")
            dist_label = f" — Relevanz: {1 / (1 + distance):.0%}" if distance is not None else ""

            with st.container(border=True):
                st.caption(f"**{filename}** (Chunk {meta.get('chunk_index', '?')}){dist_label}")
                # Show full text in small font
                st.markdown(
                    f"<div style='font-size:0.85em; max-height:200px; overflow-y:auto;'>{chunk['text']}</div>",
                    unsafe_allow_html=True,
                )


def render_chunk_search(project_id: str, key_prefix: str, on_add=None):
    """Render a chunk search interface with two modes: keyword search and source browsing.

    Args:
        project_id: Project ID for RAG search.
        key_prefix: Unique key prefix for widgets.
        on_add: Callback(chunk_dict) when user clicks "add".
                If None, no add button is shown.
    """
    mode_key = f"{key_prefix}_mode"
    mode = st.radio(
        "Suchmodus", ["Stichwort-Suche", "Quelle durchblaettern"],
        horizontal=True, key=mode_key, label_visibility="collapsed",
    )

    if mode == "Stichwort-Suche":
        _render_keyword_search(project_id, key_prefix, on_add)
    else:
        _render_source_browser(project_id, key_prefix, on_add)


def _render_keyword_search(project_id: str, key_prefix: str, on_add=None):
    """Keyword-based semantic search."""
    query = st.text_input(
        "Suchbegriff",
        placeholder="z.B. 'Antriebstechnik' oder 'market analysis'",
        key=f"{key_prefix}_search_query",
    )
    n_results = st.slider("Anzahl Ergebnisse", 1, 10, 5, key=f"{key_prefix}_search_n")

    if st.button("Suchen", key=f"{key_prefix}_search_btn") and query:
        results = search_project_sources(project_id, query, n_results=n_results)
        st.session_state[f"{key_prefix}_search_results"] = results

    results = st.session_state.get(f"{key_prefix}_search_results", [])
    if results:
        _render_chunk_results(results, key_prefix, on_add)


def _render_source_browser(project_id: str, key_prefix: str, on_add=None):
    """Browse chunks by source file."""
    from slidebuddy.config.defaults import DB_PATH
    from slidebuddy.db.migrations import get_connection
    from slidebuddy.db.queries import get_sources_for_project

    conn = get_connection(DB_PATH)
    sources = get_sources_for_project(conn, project_id)
    conn.close()

    if not sources:
        st.caption("Keine Quellen vorhanden.")
        return

    source_labels = {s.id: f"{s.filename} ({s.chunk_count or 0} Chunks)" for s in sources}
    selected_source_id = st.selectbox(
        "Quelle",
        [s.id for s in sources],
        format_func=lambda sid: source_labels.get(sid, sid),
        key=f"{key_prefix}_browse_source",
    )

    if not selected_source_id:
        return

    # Load chunks from ChromaDB for this source
    collection = get_project_sources_collection(project_id)
    if collection.count() == 0:
        st.caption("Keine Chunks in ChromaDB.")
        return

    result = collection.get(
        where={"source_id": selected_source_id},
        include=["documents", "metadatas"],
    )

    if not result["documents"]:
        st.caption("Keine Chunks fuer diese Quelle.")
        return

    # Sort by chunk_index, build chunk dicts
    paired = sorted(
        zip(result["documents"], result["metadatas"], result["ids"]),
        key=lambda x: x[1].get("chunk_index", 0),
    )

    # Optional text filter
    search_filter = st.text_input(
        "Filtern", placeholder="Text-Filter...",
        key=f"{key_prefix}_browse_filter",
    )
    if search_filter:
        search_lower = search_filter.lower()
        paired = [(doc, meta, cid) for doc, meta, cid in paired if search_lower in doc.lower()]

    st.caption(f"{len(paired)} Chunks")

    if not paired:
        return

    # Convert to standard chunk dicts and display
    chunks = [
        {"text": doc, "metadata": meta, "distance": None}
        for doc, meta, cid in paired
    ]
    _render_chunk_results(chunks, f"{key_prefix}_browse", on_add)


def _render_chunk_results(chunks: list[dict], key_prefix: str, on_add=None):
    """Render a list of chunks with optional add buttons."""
    st.caption(f"{len(chunks)} Treffer")
    for i, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})
        filename = meta.get("filename", "?")
        distance = chunk.get("distance")
        dist_label = f" — Relevanz: {1 / (1 + distance):.0%}" if distance is not None else ""

        with st.container(border=True):
            col_info, col_btn = st.columns([5, 1])
            with col_info:
                st.caption(f"**{filename}** (Chunk {meta.get('chunk_index', '?')}){dist_label}")
                st.markdown(
                    f"<div style='font-size:0.85em; max-height:150px; overflow-y:auto;'>"
                    f"{chunk['text'][:500]}{'...' if len(chunk['text']) > 500 else ''}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col_btn:
                if on_add and st.button("➕", key=f"{key_prefix}_add_{i}",
                                        help="Chunk zur Folie hinzufuegen"):
                    on_add(chunk)
                    st.rerun()
