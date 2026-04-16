import sqlite3
from typing import List

from slidebuddy.db.models import Chapter
from ._base import _parse_datetime


def _row_to_chapter(row: sqlite3.Row) -> Chapter:
    # source_segment may not exist in older DBs before migration runs
    try:
        source_segment = row["source_segment"]
    except (IndexError, KeyError):
        source_segment = None

    return Chapter(
        id=row["id"],
        project_id=row["project_id"],
        version_id=row["version_id"],
        chapter_index=row["chapter_index"],
        title=row["title"],
        summary=row["summary"],
        estimated_slide_count=row["estimated_slide_count"],
        status=row["status"],
        source_ids=row["source_ids"] or "",
        source_segment=source_segment,
    )


def create_chapter(conn: sqlite3.Connection, chapter: Chapter) -> Chapter:
    conn.execute(
        """INSERT INTO chapters
           (id, project_id, version_id, chapter_index, title, summary,
            estimated_slide_count, status, source_ids, source_segment)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            chapter.id,
            chapter.project_id,
            chapter.version_id,
            chapter.chapter_index,
            chapter.title,
            chapter.summary,
            chapter.estimated_slide_count,
            chapter.status,
            chapter.source_ids or "",
            chapter.source_segment,
        ),
    )
    conn.commit()
    return chapter


def get_chapters_for_project(
    conn: sqlite3.Connection, project_id: str
) -> List[Chapter]:
    rows = conn.execute(
        "SELECT * FROM chapters WHERE project_id = ? ORDER BY chapter_index",
        (project_id,),
    ).fetchall()
    return [_row_to_chapter(r) for r in rows]


def update_chapter_status(
    conn: sqlite3.Connection, chapter_id: str, status: str
) -> None:
    conn.execute(
        "UPDATE chapters SET status = ? WHERE id = ?",
        (status, chapter_id),
    )
    conn.commit()
