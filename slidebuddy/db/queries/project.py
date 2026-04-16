import sqlite3
from datetime import datetime
from typing import List, Optional

from slidebuddy.db.models import Project
from ._base import _parse_datetime


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
    keys = row.keys()
    return Project(
        id=row["id"],
        name=row["name"],
        topic=row["topic"],
        language=row["language"],
        prompt_override=row["prompt_override"],
        global_text_length=row["global_text_length"],
        llm_config=row["llm_config"],
        planning_prompt=row["planning_prompt"] if "planning_prompt" in keys else None,
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def get_project(conn: sqlite3.Connection, project_id: str) -> Optional[Project]:
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return _row_to_project(row) if row else None


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
               global_text_length = ?, llm_config = ?, planning_prompt = ?,
               updated_at = ?
           WHERE id = ?""",
        (
            project.name,
            project.topic,
            project.language,
            project.prompt_override,
            project.global_text_length,
            project.llm_config,
            project.planning_prompt,
            project.updated_at.isoformat(),
            project.id,
        ),
    )
    conn.commit()
    return project


def delete_project(conn: sqlite3.Connection, project_id: str) -> None:
    conn.execute("DELETE FROM source_gaps WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM slides WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM section_plans WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM chapters WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM versions WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM sources WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
