from concurrent.futures import ThreadPoolExecutor

from slidebuddy.rag.chroma_manager import get_global_slides_collection, get_project_sources_collection


def search_project_sources(project_id: str, query: str, n_results: int = 3) -> list[dict]:
    """Search project-specific source chunks."""
    collection = get_project_sources_collection(project_id)
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, count),
    )
    return _format_results(results)


def search_global_slides(query: str, language: str = "de", n_results: int = 2) -> list[dict]:
    """Search global slide collection for reusable slides.

    Tries to filter by language first; falls back to unfiltered search if the
    metadata field doesn't exist on stored documents (e.g. slides indexed
    before the language field was introduced).
    """
    collection = get_global_slides_collection()
    count = collection.count()
    if count == 0:
        return []

    effective_n = min(n_results, count)
    try:
        results = collection.query(
            query_texts=[query],
            n_results=effective_n,
            where={"language": language},
        )
    except Exception:
        # where-filter fails when documents lack the "language" metadata key
        results = collection.query(
            query_texts=[query],
            n_results=effective_n,
        )
    return _format_results(results)


def search_all(project_id: str, query: str, language: str = "de",
               n_sources: int = 3, n_global: int = 2) -> tuple[list[dict], list[dict]]:
    """Run both RAG searches in parallel using threads.

    Returns (source_chunks, global_slides). Previously these ran sequentially,
    adding ~0.5s per slide. With ThreadPoolExecutor they overlap.
    """
    with ThreadPoolExecutor(max_workers=2) as executor:
        source_future = executor.submit(search_project_sources, project_id, query, n_sources)
        global_future = executor.submit(search_global_slides, query, language, n_global)
        return source_future.result(), global_future.result()


def delete_source_chunks(project_id: str, source_id: str) -> None:
    """Remove all chunks for a source from the project collection."""
    collection = get_project_sources_collection(project_id)
    if collection.count() == 0:
        return
    results = collection.get(where={"source_id": source_id}, include=[])
    if results["ids"]:
        collection.delete(ids=results["ids"])


def add_source_chunks(project_id: str, source_id: str, chunks: list[dict], metadata: dict) -> None:
    """Add source chunks to project collection."""
    collection = get_project_sources_collection(project_id)

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        chunk_id = f"{source_id}_chunk_{chunk['chunk_index']}"
        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append({
            "source_id": source_id,
            "source_type": metadata.get("source_type", ""),
            "filename": metadata.get("filename", ""),
            "chunk_index": chunk["chunk_index"],
        })

    if ids:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)


def add_slide_to_global(slide_id: str, document: str, metadata: dict) -> None:
    """Add a finished slide to the global slides collection."""
    collection = get_global_slides_collection()
    collection.add(
        ids=[slide_id],
        documents=[document],
        metadatas=[metadata],
    )


def assign_chunks_for_slide(
    project_id: str,
    query: str,
    source_ids: list[str],
    mode: str = "chunk",
    n_results: int = 3,
    source_texts: dict[str, str] | None = None,
    slide_index: int = 0,
    total_slides: int = 1,
) -> list[dict]:
    """Route chunk assignment based on mode.

    chunk       — global semantic search across all sources (current default)
    hybrid      — semantic search within chapter sources, topped up with global
    full_source — full cleaned source text split sequentially across slides
                  (uses source_texts dict; falls back to chunk if empty)

    Falls back to "chunk" if source_ids is empty regardless of mode.
    """
    if not source_ids or mode == "chunk":
        return search_project_sources(project_id, query, n_results)

    if mode == "full_source":
        result = _get_full_source_segment(
            source_ids, source_texts or {}, slide_index, total_slides,
        )
        # Fallback to global chunk search if no original_text available
        return result if result else search_project_sources(project_id, query, n_results)

    if mode == "hybrid":
        return _search_hybrid(project_id, query, source_ids, n_results)

    # Unknown mode → global search
    return search_project_sources(project_id, query, n_results)


def _get_full_source_segment(
    source_ids: list[str],
    source_texts: dict[str, str],
    slide_index: int,
    total_slides: int,
) -> list[dict]:
    """Split full cleaned source text evenly across slides.

    Concatenates original_text for all source_ids in order, then returns the
    slice that belongs to slide_index. Each slide gets an equal share of the
    full text — total token usage across all slides equals the full document.
    """
    full_text = "\n\n".join(
        source_texts[sid] for sid in source_ids if source_texts.get(sid)
    )
    if not full_text:
        return []

    n = len(full_text)
    start = (slide_index * n) // max(total_slides, 1)
    end = ((slide_index + 1) * n) // max(total_slides, 1)
    segment = full_text[start:end].strip()

    if not segment:
        return []
    return [{"text": segment, "metadata": {"mode": "full_source"}, "distance": 0.0}]


def _search_hybrid(
    project_id: str,
    query: str,
    source_ids: list[str],
    n_results: int,
) -> list[dict]:
    """Semantic search within chapter sources, topped up from global pool.

    1. Query with ChromaDB where-filter for source_ids.
    2. If fewer than n_results found, fill remaining slots from global search.
    """
    collection = get_project_sources_collection(project_id)
    if collection.count() == 0:
        return []

    where = (
        {"source_id": {"$in": source_ids}}
        if len(source_ids) > 1
        else {"source_id": source_ids[0]}
    )
    try:
        results = _format_results(
            collection.query(
                query_texts=[query],
                n_results=min(n_results, collection.count()),
                where=where,
            )
        )
    except Exception:
        results = []

    if len(results) < n_results:
        seen = {
            r["metadata"].get("source_id", "") + str(r["metadata"].get("chunk_index", ""))
            for r in results
        }
        for r in search_project_sources(project_id, query, n_results):
            key = r["metadata"].get("source_id", "") + str(r["metadata"].get("chunk_index", ""))
            if key not in seen:
                results.append(r)
                seen.add(key)
                if len(results) >= n_results:
                    break

    return results[:n_results]


def _format_results(results: dict) -> list[dict]:
    """Format ChromaDB query results into a clean list."""
    if not results or not results.get("documents") or not results["documents"][0]:
        return []

    formatted = []
    for i, doc in enumerate(results["documents"][0]):
        entry = {
            "text": doc,
            "distance": results["distances"][0][i] if results.get("distances") else None,
            "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
        }
        formatted.append(entry)
    # Sort by distance ascending (most relevant first)
    formatted.sort(key=lambda c: c["distance"] if c["distance"] is not None else float("inf"))
    return formatted
