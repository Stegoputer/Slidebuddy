import json
import sqlite3
from datetime import datetime

from slidebuddy.db.models import new_id


def save_section_plan(
    conn: sqlite3.Connection,
    project_id: str,
    chapter_index: int,
    data: dict | list,
) -> None:
    """Persist a section plan for a chapter (upsert by project_id + chapter_index)."""
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO section_plans (id, project_id, chapter_index, slides_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(project_id, chapter_index)
           DO UPDATE SET slides_json = excluded.slides_json, updated_at = excluded.updated_at""",
        (new_id(), project_id, chapter_index, json.dumps(data, ensure_ascii=False), now, now),
    )
    conn.commit()


def get_section_plan(
    conn: sqlite3.Connection,
    project_id: str,
    chapter_index: int,
) -> dict | list | None:
    """Load a single section plan; returns None if not found."""
    row = conn.execute(
        "SELECT slides_json FROM section_plans WHERE project_id = ? AND chapter_index = ?",
        (project_id, chapter_index),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["slides_json"])


def get_all_section_plans(
    conn: sqlite3.Connection,
    project_id: str,
) -> dict[int, dict | list]:
    """Return all section plans for a project as {chapter_index: data}."""
    rows = conn.execute(
        "SELECT chapter_index, slides_json FROM section_plans WHERE project_id = ? ORDER BY chapter_index",
        (project_id,),
    ).fetchall()
    return {row["chapter_index"]: json.loads(row["slides_json"]) for row in rows}


def delete_section_plans_for_project(
    conn: sqlite3.Connection,
    project_id: str,
) -> None:
    """Delete all section plans for a project."""
    conn.execute("DELETE FROM section_plans WHERE project_id = ?", (project_id,))
    conn.commit()
