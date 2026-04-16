import sqlite3
from typing import List

from slidebuddy.db.models import Version
from ._base import _parse_datetime


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
