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
            dist_label = f" — Relevanz: {1 - distance:.0%}" if distance is not None else ""

            with st.container(border=True):
                st.caption(f"**{filename}** (Chunk {meta.get('chunk_index', '?')}){dist_label}")
                # Show full text in small font
                st.markdown(
                    f"<div style='font-size:0.85em; max-height:200px; overflow-y:auto;'>{chunk['text']}</div>",
                    unsafe_allow_html=True,
                )


def render_chunk_search(project_id: str, key_prefix: str, on_add=None):
    """Render a chunk search interface with option to add chunks to a list.

    Args:
        project_id: Project ID for RAG search.
        key_prefix: Unique key prefix for widgets.
        on_add: Callback(chunk_dict) when user clicks "add".
                If None, no add button is shown.
    """
    with st.expander("🔍 Quellen durchsuchen & hinzufuegen", expanded=False):
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
            st.caption(f"{len(results)} Treffer")
            for i, chunk in enumerate(results):
                meta = chunk.get("metadata", {})
                filename = meta.get("filename", "?")
                distance = chunk.get("distance")
                dist_label = f" — Relevanz: {1 - distance:.0%}" if distance is not None else ""

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


def render_pinned_chunks(chunks: list[dict], key_prefix: str, on_remove=None):
    """Show manually pinned chunks with option to remove."""
    if not chunks:
        return
    st.caption(f"📌 {len(chunks)} manuell hinzugefuegte Chunks")
    for i, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})
        filename = meta.get("filename", "?")
        col_info, col_del = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"<div style='font-size:0.85em;'>"
                f"<b>{filename}</b> (Chunk {meta.get('chunk_index', '?')}): "
                f"{chunk['text'][:120]}...</div>",
                unsafe_allow_html=True,
            )
        with col_del:
            if on_remove and st.button("🗑️", key=f"{key_prefix}_unpin_{i}"):
                on_remove(i)
                st.rerun()
