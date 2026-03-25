import sqlite3
from datetime import datetime
from typing import List, Optional

from .models import (
    Chapter,
    MasterTemplate,
    Project,
    Slide,
    SlideMaster,
    Source,
    SourceGap,
    Version,
)


def _parse_datetime(value: str | datetime | None) -> datetime:
    """Parse a datetime string from SQLite into a datetime object."""
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.utcnow()


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

def create_project(conn: sqlite3.Connection, project: Project) -> Project:
    conn.execute(
        """INSERT INTO projects
           (id, name, topic, language, prompt_override, global_text_length,
            llm_config, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            project.id,
            project.name,
            project.topic,
            project.language,
            project.prompt_override,
            project.global_text_length,
            project.llm_config,
            project.created_at.isoformat(),
            project.updated_at.isoformat(),
        ),
    )
    conn.commit()
    return project


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        topic=row["topic"],
        language=row["language"],
        prompt_override=row["prompt_override"],
        global_text_length=row["global_text_length"],
        llm_config=row["llm_config"],
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def get_project(conn: sqlite3.Connection, project_id: str) -> Optional[Project]:
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_project(row)


def get_all_projects(conn: sqlite3.Connection) -> List[Project]:
    rows = conn.execute(
        "SELECT * FROM projects ORDER BY created_at DESC"
    ).fetchall()
    return [_row_to_project(r) for r in rows]


def update_project(conn: sqlite3.Connection, project: Project) -> Project:
    project.updated_at = datetime.utcnow()
    conn.execute(
        """UPDATE projects
           SET name = ?, topic = ?, language = ?, prompt_override = ?,
               global_text_length = ?, llm_config = ?, updated_at = ?
           WHERE id = ?""",
        (
            project.name,
            project.topic,
            project.language,
            project.prompt_override,
            project.global_text_length,
            project.llm_config,
            project.updated_at.isoformat(),
            project.id,
        ),
    )
    conn.commit()
    return project


def delete_project(conn: sqlite3.Connection, project_id: str) -> None:
    conn.execute("DELETE FROM source_gaps WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM slides WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM chapters WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM versions WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM sources WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Source CRUD
# ---------------------------------------------------------------------------

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
) -> None:
    if chunk_count is not None:
        conn.execute(
            """UPDATE sources
               SET processing_status = ?, error_message = ?, chunk_count = ?
               WHERE id = ?""",
            (status, error_message, chunk_count, source_id),
        )
    else:
        conn.execute(
            """UPDATE sources
               SET processing_status = ?, error_message = ?
               WHERE id = ?""",
            (status, error_message, source_id),
        )
    conn.commit()


def delete_source(conn: sqlite3.Connection, source_id: str) -> None:
    conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Chapter CRUD
# ---------------------------------------------------------------------------

def _row_to_chapter(row: sqlite3.Row) -> Chapter:
    return Chapter(
        id=row["id"],
        project_id=row["project_id"],
        version_id=row["version_id"],
        chapter_index=row["chapter_index"],
        title=row["title"],
        summary=row["summary"],
        estimated_slide_count=row["estimated_slide_count"],
        status=row["status"],
    )


def create_chapter(conn: sqlite3.Connection, chapter: Chapter) -> Chapter:
    conn.execute(
        """INSERT INTO chapters
           (id, project_id, version_id, chapter_index, title, summary,
            estimated_slide_count, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            chapter.id,
            chapter.project_id,
            chapter.version_id,
            chapter.chapter_index,
            chapter.title,
            chapter.summary,
            chapter.estimated_slide_count,
            chapter.status,
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


# ---------------------------------------------------------------------------
# Slide CRUD
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Version CRUD
# ---------------------------------------------------------------------------

def _row_to_version(row: sqlite3.Row) -> Version:
    return Version(
        id=row["id"],
        project_id=row["project_id"],
        chapter_index=row["chapter_index"],
        version_number=row["version_number"],
        state=row["state"],
        state_json=row["state_json"],
        created_at=_parse_datetime(row["created_at"]),
    )


def create_version(conn: sqlite3.Connection, version: Version) -> Version:
    conn.execute(
        """INSERT INTO versions
           (id, project_id, chapter_index, version_number, state,
            state_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            version.id,
            version.project_id,
            version.chapter_index,
            version.version_number,
            version.state,
            version.state_json,
            version.created_at.isoformat(),
        ),
    )
    conn.commit()
    return version


def get_versions_for_project(
    conn: sqlite3.Connection, project_id: str
) -> List[Version]:
    rows = conn.execute(
        "SELECT * FROM versions WHERE project_id = ? ORDER BY chapter_index, version_number",
        (project_id,),
    ).fetchall()
    return [_row_to_version(r) for r in rows]


# ---------------------------------------------------------------------------
# SourceGap CRUD
# ---------------------------------------------------------------------------

def _row_to_source_gap(row: sqlite3.Row) -> SourceGap:
    return SourceGap(
        id=row["id"],
        project_id=row["project_id"],
        chapter_id=row["chapter_id"],
        description=row["description"],
        status=row["status"],
        created_at=_parse_datetime(row["created_at"]),
    )


def create_source_gap(
    conn: sqlite3.Connection, gap: SourceGap
) -> SourceGap:
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


# ---------------------------------------------------------------------------
# SlideMaster CRUD
# ---------------------------------------------------------------------------

def _row_to_slide_master(row: sqlite3.Row) -> SlideMaster:
    return SlideMaster(
        id=row["id"],
        name=row["name"],
        filename=row["filename"],
        file_path=row["file_path"],
        is_active=bool(row["is_active"]),
        created_at=_parse_datetime(row["created_at"]),
    )


def create_slide_master(conn: sqlite3.Connection, master: SlideMaster) -> SlideMaster:
    conn.execute(
        """INSERT INTO slide_masters (id, name, filename, file_path, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (master.id, master.name, master.filename, master.file_path,
         master.is_active, master.created_at.isoformat()),
    )
    conn.commit()
    return master


def get_all_slide_masters(conn: sqlite3.Connection) -> List[SlideMaster]:
    rows = conn.execute(
        "SELECT * FROM slide_masters ORDER BY created_at DESC"
    ).fetchall()
    return [_row_to_slide_master(r) for r in rows]


def get_slide_master(conn: sqlite3.Connection, master_id: str) -> Optional[SlideMaster]:
    row = conn.execute(
        "SELECT * FROM slide_masters WHERE id = ?", (master_id,)
    ).fetchone()
    return _row_to_slide_master(row) if row else None


def get_active_slide_master(conn: sqlite3.Connection) -> Optional[SlideMaster]:
    row = conn.execute(
        "SELECT * FROM slide_masters WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    return _row_to_slide_master(row) if row else None


def set_active_slide_master(conn: sqlite3.Connection, master_id: str | None) -> None:
    """Set a master as active (deactivate all others). Pass None to use defaults."""
    conn.execute("UPDATE slide_masters SET is_active = 0")
    if master_id:
        conn.execute("UPDATE slide_masters SET is_active = 1 WHERE id = ?", (master_id,))
    conn.commit()


def delete_slide_master(conn: sqlite3.Connection, master_id: str) -> None:
    conn.execute("DELETE FROM master_templates WHERE master_id = ?", (master_id,))
    conn.execute("DELETE FROM slide_masters WHERE id = ?", (master_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# MasterTemplate CRUD
# ---------------------------------------------------------------------------

def _row_to_master_template(row: sqlite3.Row) -> MasterTemplate:
    return MasterTemplate(
        id=row["id"],
        master_id=row["master_id"],
        layout_index=row["layout_index"],
        layout_name=row["layout_name"],
        template_key=row["template_key"],
        display_name=row["display_name"],
        description=row["description"],
        placeholder_schema=row["placeholder_schema"],
        content_schema=row["content_schema"],
        generation_prompt=row["generation_prompt"],
        is_active=bool(row["is_active"]),
        created_at=_parse_datetime(row["created_at"]),
    )


def create_master_template(conn: sqlite3.Connection, tpl: MasterTemplate) -> MasterTemplate:
    conn.execute(
        """INSERT INTO master_templates
           (id, master_id, layout_index, layout_name, template_key, display_name,
            description, placeholder_schema, content_schema, generation_prompt,
            is_active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tpl.id, tpl.master_id, tpl.layout_index, tpl.layout_name,
         tpl.template_key, tpl.display_name, tpl.description,
         tpl.placeholder_schema, tpl.content_schema, tpl.generation_prompt,
         tpl.is_active, tpl.created_at.isoformat()),
    )
    conn.commit()
    return tpl


def get_templates_for_master(conn: sqlite3.Connection, master_id: str) -> List[MasterTemplate]:
    rows = conn.execute(
        "SELECT * FROM master_templates WHERE master_id = ? ORDER BY layout_index",
        (master_id,),
    ).fetchall()
    return [_row_to_master_template(r) for r in rows]


def get_active_master_templates(conn: sqlite3.Connection) -> List[MasterTemplate]:
    """Get templates from the currently active slide master."""
    rows = conn.execute(
        """SELECT mt.* FROM master_templates mt
           JOIN slide_masters sm ON mt.master_id = sm.id
           WHERE sm.is_active = 1 AND mt.is_active = 1
           ORDER BY mt.layout_index""",
    ).fetchall()
    return [_row_to_master_template(r) for r in rows]


def update_master_template(conn: sqlite3.Connection, tpl: MasterTemplate) -> MasterTemplate:
    conn.execute(
        """UPDATE master_templates
           SET display_name = ?, description = ?, content_schema = ?,
               generation_prompt = ?, is_active = ?, template_key = ?
           WHERE id = ?""",
        (tpl.display_name, tpl.description, tpl.content_schema,
         tpl.generation_prompt, tpl.is_active, tpl.template_key, tpl.id),
    )
    conn.commit()
    return tpl
