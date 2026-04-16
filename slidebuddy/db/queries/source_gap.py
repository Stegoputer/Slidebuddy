import sqlite3
from typing import List

from slidebuddy.db.models import SourceGap
from ._base import _parse_datetime


def _row_to_source_gap(row: sqlite3.Row) -> SourceGap:
    return SourceGap(
        id=row["id"],
        project_id=row["project_id"],
        chapter_id=row["chapter_id"],
        description=row["description"],
        status=row["status"],
        created_at=_parse_datetime(row["created_at"]),
    )


def create_source_gap(conn: sqlite3.Connection, gap: SourceGap) -> SourceGap:
    conn.execute(
        """INSERT INTO source_gaps
           (id, project_id, chapter_id, description, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            gap.id,
            gap.project_id,
            gap.chapter_id,
            gap.description,
            gap.status,
            gap.created_at.isoformat(),
        ),
    )
    conn.commit()
    return gap


def get_source_gaps_for_project(
    conn: sqlite3.Connection, project_id: str
) -> List[SourceGap]:
    rows = conn.execute(
        "SELECT * FROM source_gaps WHERE project_id = ? ORDER BY created_at",
        (project_id,),
    ).fetchall()
    return [_row_to_source_gap(r) for r in rows]


def update_source_gap_status(
    conn: sqlite3.Connection, gap_id: str, status: str
) -> None:
    conn.execute(
        "UPDATE source_gaps SET status = ? WHERE id = ?",
        (status, gap_id),
    )
    conn.commit()
