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
        metadata={"hnsw:space": "cosine", "description": "All slides across all projects"},
    )


def get_project_sources_collection(project_id: str):
    """Get or create the project-specific sources collection."""
    client = get_client()
    collection_name = f"project_{project_id}_sources"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine", "description": f"Source chunks for project {project_id}"},
    )


def delete_project_sources_collection(project_id: str) -> None:
    """Delete a project's source collection."""
    client = get_client()
    collection_name = f"project_{project_id}_sources"
    try:
        client.delete_collection(collection_name)
    except ValueError:
        pass  # Collection doesn't exist


def migrate_to_cosine() -> int:
    """Migrate all existing collections from L2 to cosine distance.

    Returns the number of collections migrated.
    """
    client = get_client()
    migrated = 0
    for col_ref in client.list_collections():
        col = client.get_collection(col_ref.name)
        meta = col.metadata or {}
        if meta.get("hnsw:space") == "cosine":
            continue  # Already cosine

        count = col.count()
        if count == 0:
            client.delete_collection(col_ref.name)
            client.get_or_create_collection(
                name=col_ref.name,
                metadata={**meta, "hnsw:space": "cosine"},
            )
            migrated += 1
            continue

        # Read all data
        data = col.get(include=["documents", "metadatas", "embeddings"])
        ids = data["ids"]
        docs = data["documents"]
        metas = data["metadatas"]
        embeddings = data["embeddings"]

        # Recreate with cosine
        client.delete_collection(col_ref.name)
        new_col = client.get_or_create_collection(
            name=col_ref.name,
            metadata={**meta, "hnsw:space": "cosine"},
        )
        if ids:
            new_col.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
        migrated += 1

    return migrated


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
