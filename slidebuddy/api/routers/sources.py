"""Source upload and management endpoints."""

import logging
import sqlite3

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from slidebuddy.config.defaults import UPLOADS_DIR, load_preferences
from slidebuddy.db.models import Source
from slidebuddy.db.queries import (
    create_source,
    delete_source,
    get_sources_for_project,
    update_source_status,
)
from slidebuddy.parsers import SUPPORTED_EXTENSIONS, get_source_type, parse_source
from slidebuddy.rag.chroma_manager import get_project_sources_collection, get_project_sources_collection_readonly
from slidebuddy.rag.chunking import chunk_text

from ..dependencies import get_db
from ..schemas import SourceOut, YouTubeRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def _source_to_out(s: Source) -> SourceOut:
    return SourceOut(
        id=s.id, project_id=s.project_id, source_type=s.source_type,
        filename=s.filename, chunk_count=s.chunk_count,
        processing_status=s.processing_status,
        error_message=s.error_message, created_at=s.created_at,
    )


@router.get("/{project_id}/sources", response_model=list[SourceOut])
def list_sources(project_id: str, conn=Depends(get_db)):
    return [_source_to_out(s) for s in get_sources_for_project(conn, project_id)]


@router.post("/{project_id}/sources/upload", response_model=list[SourceOut])
def upload_sources(
    project_id: str,
    files: list[UploadFile] = File(...),
    conn: sqlite3.Connection = Depends(get_db),
):
    upload_dir = UPLOADS_DIR / project_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Load preferences with fallback — corrupt prefs should not crash the upload
    try:
        prefs = load_preferences()
    except Exception as e:
        logger.warning("load_preferences() failed, using defaults: %s", e)
        prefs = {}
    rag_conf = prefs.get("rag", {})
    chunk_size = rag_conf.get("chunk_size", 500)
    chunk_overlap = rag_conf.get("chunk_overlap", 20)

    # Pre-flight: verify embedding function is available before touching any file.
    # Otherwise we'd fail mid-loop with a cryptic RuntimeError on the first chunk.
    try:
        from slidebuddy.rag.embeddings import get_embedding_function
        get_embedding_function()
    except RuntimeError as e:
        raise HTTPException(
            400,
            f"Kein Embedding-Key konfiguriert. Bitte in Einstellungen einen OpenAI- "
            f"oder Google-API-Key hinterlegen. ({e})",
        )
    except Exception as e:
        logger.error("Embedding function init failed: %s", e, exc_info=True)
        raise HTTPException(500, f"Embedding-Initialisierung fehlgeschlagen: {e}")

    # Pre-validate all extensions before touching the DB or disk
    for file in files:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(400, f"Nicht unterstützter Dateityp: {ext}")

    # Read all file contents upfront (UploadFile streams must be read while the
    # request is still open; afterwards each file is processed independently)
    file_contents: list[tuple[str, bytes]] = []
    for file in files:
        file_contents.append((file.filename, file.file.read()))

    results = []
    for filename, content in file_contents:
        source = Source(
            project_id=project_id,
            source_type="txt",  # Will be updated after path is known
            filename=filename,
        )
        try:
            # Write file to disk
            file_path = upload_dir / filename
            file_path.write_bytes(content)

            source.source_type = get_source_type(file_path) or "txt"
            create_source(conn, source)

            # Parse, chunk, and index
            text = parse_source(file_path)
            chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)

            if chunks:
                collection = get_project_sources_collection(project_id)
                collection.add(
                    ids=[f"{source.id}_chunk_{c['chunk_index']}" for c in chunks],
                    documents=[c["text"] for c in chunks],
                    metadatas=[{
                        "source_id": source.id,
                        "filename": filename,
                        "chunk_index": c["chunk_index"],
                    } for c in chunks],
                )

            update_source_status(conn, source.id, "done",
                                 chunk_count=len(chunks), original_text=text)
            source.processing_status = "done"
            source.chunk_count = len(chunks)
            source.original_text = text

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Fehler bei Verarbeitung von %s: %s", filename, e, exc_info=True)
            # Only update DB status if the source record was already created
            if source.id:
                try:
                    update_source_status(conn, source.id, "error", error_message=str(e))
                except Exception:
                    pass
            source.processing_status = "error"
            source.error_message = str(e)

        results.append(_source_to_out(source))

    return results


@router.post("/{project_id}/sources/youtube", response_model=SourceOut)
def add_youtube(project_id: str, body: YouTubeRequest, conn=Depends(get_db)):
    prefs = load_preferences()
    rag_conf = prefs.get("rag", {})
    chunk_size = rag_conf.get("chunk_size", 500)
    chunk_overlap = rag_conf.get("chunk_overlap", 20)

    source = Source(
        project_id=project_id,
        source_type="youtube",
        filename=body.url,
    )
    create_source(conn, source)

    try:
        from slidebuddy.parsers.youtube_parser import parse_youtube, get_youtube_metadata

        # Fetch real video title
        meta = get_youtube_metadata(body.url)
        if meta.get("title") and meta["title"] != "Unbekannt":
            source.filename = meta["title"]
            conn.execute("UPDATE sources SET filename=? WHERE id=?", (source.filename, source.id))
            conn.commit()

        text = parse_youtube(body.url)
        if not text:
            raise ValueError("Keine Untertitel für diese URL verfügbar (Video hat keine Untertitel oder ist privat).")
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)

        if chunks:
            collection = get_project_sources_collection(project_id)
            collection.add(
                ids=[f"{source.id}_chunk_{c['chunk_index']}" for c in chunks],
                documents=[c["text"] for c in chunks],
                metadatas=[{"source_id": source.id, "filename": body.url, "chunk_index": c["chunk_index"]} for c in chunks],
            )

        update_source_status(conn, source.id, "done", chunk_count=len(chunks), original_text=text)
        source.processing_status = "done"
        source.chunk_count = len(chunks)
    except Exception as e:
        logger.error("YouTube fetch failed: %s", e)
        update_source_status(conn, source.id, "error", error_message=str(e))
        source.processing_status = "error"
        source.error_message = str(e)

    return _source_to_out(source)


@router.post("/{project_id}/sources/{source_id}/repair")
def repair_source(project_id: str, source_id: str, conn=Depends(get_db)):
    """Re-fetch original_text for sources that are missing it (e.g. old YouTube uploads)."""
    sources = get_sources_for_project(conn, project_id)
    source = next((s for s in sources if s.id == source_id), None)
    if not source:
        raise HTTPException(404, "Source not found")
    if source.original_text:
        return {"status": "ok", "message": "original_text already present", "text_len": len(source.original_text)}

    if source.source_type == "youtube":
        from slidebuddy.parsers.youtube_parser import parse_youtube
        text = parse_youtube(source.filename)
        if not text:
            raise HTTPException(400, "Keine Untertitel verfügbar")
        update_source_status(conn, source_id, "done", original_text=text)
        return {"status": "repaired", "text_len": len(text)}

    raise HTTPException(400, f"Repair not supported for source type: {source.source_type}")


@router.delete("/{project_id}/sources/{source_id}", status_code=204)
def remove_source(project_id: str, source_id: str, conn=Depends(get_db)):
    # Remove chunks from ChromaDB
    try:
        collection = get_project_sources_collection(project_id)
        existing = collection.get(where={"source_id": source_id})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass
    delete_source(conn, source_id)


# ---------------------------------------------------------------------------
# Chunk Browser
# ---------------------------------------------------------------------------

@router.get("/{project_id}/sources/{source_id}/chunks")
def get_chunks(project_id: str, source_id: str, search: str = ""):
    """Return all chunks for a source, optionally filtered by search term."""
    try:
        collection = get_project_sources_collection_readonly(project_id)
    except Exception as e:
        raise HTTPException(404, f"Collection not found: {e}")

    try:
        result = collection.get(
            where={"source_id": source_id},
            include=["documents", "metadatas"],
            limit=collection.count() or 1,
        )
    except Exception as e:
        raise HTTPException(500, f"ChromaDB error: {e}")

    if not result["documents"]:
        return []

    # Pair and sort by chunk_index
    paired = list(zip(result["documents"], result["metadatas"], result["ids"]))
    paired.sort(key=lambda x: x[1].get("chunk_index", 0))

    # Optional search filter
    if search:
        search_lower = search.lower()
        paired = [(doc, meta, cid) for doc, meta, cid in paired if search_lower in doc.lower()]

    return [
        {
            "id": cid,
            "text": doc,
            "metadata": meta,
            "char_count": len(doc),
            "token_estimate": len(doc) // 4,
        }
        for doc, meta, cid in paired
    ]
