import chromadb
from pathlib import Path
from slidebuddy.config.defaults import CHROMA_DIR


_client: chromadb.ClientAPI | None = None


def get_client() -> chromadb.ClientAPI:
    """Get or create persistent ChromaDB client."""
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def get_global_slides_collection():
    """Get or create the global slides collection."""
    client = get_client()
    return client.get_or_create_collection(
        name="global_slides",
        metadata={"description": "All slides across all projects"},
    )


def get_project_sources_collection(project_id: str):
    """Get or create the project-specific sources collection."""
    client = get_client()
    collection_name = f"project_{project_id}_sources"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"description": f"Source chunks for project {project_id}"},
    )


def delete_project_sources_collection(project_id: str) -> None:
    """Delete a project's source collection."""
    client = get_client()
    collection_name = f"project_{project_id}_sources"
    try:
        client.delete_collection(collection_name)
    except ValueError:
        pass  # Collection doesn't exist


def get_collection_stats() -> dict:
    """Get statistics about ChromaDB collections.

    Note: count() per collection can be slow. This function is best
    called behind a cache (e.g. st.cache_data with TTL).
    """
    client = get_client()
    collections = client.list_collections()
    total = len(collections)
    col_stats = []
    for col in collections:
        try:
            count = client.get_collection(col.name).count()
        except Exception:
            count = 0
        col_stats.append({"name": col.name, "count": count})
    return {"total_collections": total, "collections": col_stats}
