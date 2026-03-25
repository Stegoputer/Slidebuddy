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
    """Search global slide collection for reusable slides."""
    collection = get_global_slides_collection()
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, count),
        where={"language": language},
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
    return formatted
