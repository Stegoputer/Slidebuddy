import sqlite3
from datetime import datetime
from typing import List

from slidebuddy.db.models import Slide
from ._base import _parse_datetime


def _row_to_slide(row: sqlite3.Row) -> Slide:
    return Slide(
        id=row["id"],
        chapter_id=row["chapter_id"],
        project_id=row["project_id"],
        slide_index=row["slide_index"],
        slide_index_in_chapter=row["slide_index_in_chapter"],
        template_type=row["template_type"],
        title=row["title"],
        subtitle=row["subtitle"],
        content_json=row["content_json"],
        speaker_notes=row["speaker_notes"],
        chain_of_thought=row["chain_of_thought"],
        is_reused=bool(row["is_reused"]),
        source_slide_id=row["source_slide_id"],
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def create_slide(conn: sqlite3.Connection, slide: Slide) -> Slide:
    conn.execute(
        """INSERT INTO slides
           (id, chapter_id, project_id, slide_index, slide_index_in_chapter,
            template_type, title, subtitle, content_json, speaker_notes,
            chain_of_thought, is_reused, source_slide_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            slide.id,
            slide.chapter_id,
            slide.project_id,
            slide.slide_index,
            slide.slide_index_in_chapter,
            slide.template_type,
            slide.title,
            slide.subtitle,
            slide.content_json,
            slide.speaker_notes,
            slide.chain_of_thought,
            slide.is_reused,
            slide.source_slide_id,
            slide.created_at.isoformat(),
            slide.updated_at.isoformat(),
        ),
    )
    conn.commit()
    return slide


def get_slides_for_chapter(
    conn: sqlite3.Connection, chapter_id: str
) -> List[Slide]:
    rows = conn.execute(
        "SELECT * FROM slides WHERE chapter_id = ? ORDER BY slide_index_in_chapter",
        (chapter_id,),
    ).fetchall()
    return [_row_to_slide(r) for r in rows]


def get_slides_for_project(
    conn: sqlite3.Connection, project_id: str
) -> List[Slide]:
    rows = conn.execute(
        "SELECT * FROM slides WHERE project_id = ? ORDER BY slide_index",
        (project_id,),
    ).fetchall()
    return [_row_to_slide(r) for r in rows]


def update_slide(conn: sqlite3.Connection, slide: Slide) -> Slide:
    slide.updated_at = datetime.utcnow()
    conn.execute(
        """UPDATE slides
           SET chapter_id = ?, slide_index = ?, slide_index_in_chapter = ?,
               template_type = ?, title = ?, subtitle = ?, content_json = ?,
               speaker_notes = ?, chain_of_thought = ?, is_reused = ?,
               source_slide_id = ?, updated_at = ?
           WHERE id = ?""",
        (
            slide.chapter_id,
            slide.slide_index,
            slide.slide_index_in_chapter,
            slide.template_type,
            slide.title,
            slide.subtitle,
            slide.content_json,
            slide.speaker_notes,
            slide.chain_of_thought,
            slide.is_reused,
            slide.source_slide_id,
            slide.updated_at.isoformat(),
            slide.id,
        ),
    )
    conn.commit()
    return slide
