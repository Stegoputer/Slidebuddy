import sqlite3
from typing import List, Optional

from slidebuddy.db.models import Source
from ._base import _parse_datetime


def _row_to_source(row: sqlite3.Row) -> Source:
    return Source(
        id=row["id"],
        project_id=row["project_id"],
        source_type=row["source_type"],
        filename=row["filename"],
        original_text=row["original_text"],
        chunk_count=row["chunk_count"],
        processing_status=row["processing_status"],
        error_message=row["error_message"],
        created_at=_parse_datetime(row["created_at"]),
    )


def create_source(conn: sqlite3.Connection, source: Source) -> Source:
    conn.execute(
        """INSERT INTO sources
           (id, project_id, source_type, filename, original_text,
            chunk_count, processing_status, error_message, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            source.id,
            source.project_id,
            source.source_type,
            source.filename,
            source.original_text,
            source.chunk_count,
            source.processing_status,
            source.error_message,
            source.created_at.isoformat(),
        ),
    )
    conn.commit()
    return source


def get_sources_for_project(
    conn: sqlite3.Connection, project_id: str
) -> List[Source]:
    rows = conn.execute(
        "SELECT * FROM sources WHERE project_id = ? ORDER BY created_at",
        (project_id,),
    ).fetchall()
    return [_row_to_source(r) for r in rows]


def update_source_status(
    conn: sqlite3.Connection,
    source_id: str,
    status: str,
    error_message: Optional[str] = None,
    chunk_count: Optional[int] = None,
    original_text: Optional[str] = None,
) -> None:
    fields = ["processing_status = ?"]
    values: list = [status]
    if error_message is not None:
        fields.append("error_message = ?")
        values.append(error_message)
    if chunk_count is not None:
        fields.append("chunk_count = ?")
        values.append(chunk_count)
    if original_text is not None:
        fields.append("original_text = ?")
        values.append(original_text)
    values.append(source_id)
    conn.execute(
        f"UPDATE sources SET {', '.join(fields)} WHERE id = ?",
        values,
    )
    conn.commit()


def delete_source(conn: sqlite3.Connection, source_id: str) -> None:
    conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    conn.commit()
