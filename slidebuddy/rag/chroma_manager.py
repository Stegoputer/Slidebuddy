import logging
import threading

from slidebuddy.config.defaults import CHROMA_DIR

_logger = logging.getLogger(__name__)
_client = None
_client_lock = threading.Lock()


def get_client():
    """Get or create persistent ChromaDB client (thread-safe).

    Uses double-checked locking so that parallel RAG searches (ThreadPoolExecutor)
    cannot both see _client=None and race to create two PersistentClient instances
    for the same path — which causes ChromaDB to raise KeyError(path).
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                import chromadb
                CHROMA_DIR.mkdir(parents=True, exist_ok=True)
                _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def _resolve_collection(name: str, embedding_function, metadata: dict):
    """Get or create a collection, auto-migrating if the embedding function changed.

    ChromaDB raises ValueError when an existing collection was created with a different
    embedding function (e.g. "default" ONNX vs. "openai"). When that happens:
      1. Read all stored documents + metadata — NOT the old vectors, which are
         model-specific and therefore incompatible with the new embedding model.
      2. Delete the old collection.
      3. Recreate with the correct embedding function.
      4. Re-add the documents so ChromaDB recomputes vectors with the new model.

    This is a transparent, one-time migration per collection.
    """
    client = get_client()
    try:
        return client.get_or_create_collection(
            name=name,
            embedding_function=embedding_function,
            metadata=metadata,
        )
    except ValueError as e:
        if "Embedding function conflict" not in str(e):
            raise

        _logger.warning(
            "Embedding function conflict on '%s' — migrating to new embedding model.", name
        )

        # Read documents + metadata without embedding (old vectors are model-specific, discard them)
        old_col = client.get_collection(name=name)
        data = old_col.get(include=["documents", "metadatas"])
        ids = data["ids"]
        docs = data["documents"]
        metas = data["metadatas"]

        # Rebuild with correct embedding function
        client.delete_collection(name=name)
        new_col = client.get_or_create_collection(
            name=name,
            embedding_function=embedding_function,
            metadata=metadata,
        )

        # Re-index: ChromaDB calls the new embedding function to compute fresh vectors
        if ids:
            _logger.info("Re-indexing %d documents in '%s' with new embedding model.", len(ids), name)
            new_col.add(ids=ids, documents=docs, metadatas=metas)

        return new_col


def get_global_slides_collection():
    """Get or create the global slides collection."""
    from slidebuddy.rag.embeddings import get_embedding_function
    ef = get_embedding_function()
    return _resolve_collection(
        name="global_slides",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine", "description": "All slides across all projects"},
    )


def get_project_sources_collection(project_id: str):
    """Get or create the project-specific sources collection."""
    from slidebuddy.rag.embeddings import get_embedding_function
    ef = get_embedding_function()
    collection_name = f"project_{project_id}_sources"
    return _resolve_collection(
        name=collection_name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine", "description": f"Source chunks for project {project_id}"},
    )


def get_project_sources_collection_readonly(project_id: str):
    """Get existing collection without embedding (for read-only ops: chunk browser, delete by ID)."""
    client = get_client()
    collection_name = f"project_{project_id}_sources"
    return client.get_collection(name=collection_name)


def delete_project_sources_collection(project_id: str) -> None:
    """Delete a project's source collection."""
    client = get_client()
    collection_name = f"project_{project_id}_sources"
    try:
        client.delete_collection(collection_name)
    except ValueError:
        pass  # Collection doesn't exist — nothing to do


def migrate_to_cosine() -> int:
    """Migrate all existing collections from L2 to cosine distance.

    Also fixes embedding-function conflicts: collections that were created without
    an explicit embedding_function (persisted as 'default') are rebuilt with the
    currently configured embedding model.

    Returns the number of collections migrated.
    """
    from slidebuddy.rag.embeddings import get_embedding_function
    client = get_client()
    ef = get_embedding_function()
    migrated = 0

    for col_ref in client.list_collections():
        # Open without embedding to safely read metadata without triggering a conflict
        try:
            col = client.get_collection(col_ref.name)
        except Exception:
            continue

        meta = col.metadata or {}
        if meta.get("hnsw:space") == "cosine":
            continue  # Already cosine — nothing to do

        count = col.count()
        new_meta = {**meta, "hnsw:space": "cosine"}

        if count == 0:
            client.delete_collection(col_ref.name)
            client.get_or_create_collection(
                name=col_ref.name,
                embedding_function=ef,
                metadata=new_meta,
            )
            migrated += 1
            continue

        # Read documents + metadata only (old embeddings are model-specific — recompute)
        data = col.get(include=["documents", "metadatas"])
        ids = data["ids"]
        docs = data["documents"]
        metas = data["metadatas"]

        client.delete_collection(col_ref.name)
        new_col = client.get_or_create_collection(
            name=col_ref.name,
            embedding_function=ef,
            metadata=new_meta,
        )
        if ids:
            new_col.add(ids=ids, documents=docs, metadatas=metas)
        migrated += 1

    return migrated


def get_collection_stats() -> dict:
    """Get statistics about ChromaDB collections."""
    client = get_client()
    collections = client.list_collections()
    col_stats = []
    for col in collections:
        try:
            count = client.get_collection(col.name).count()
        except Exception:
            count = 0
        col_stats.append({"name": col.name, "count": count})
    return {"total_collections": len(collections), "collections": col_stats}
