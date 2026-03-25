"""Shared database helper functions for version state persistence.

Eliminates duplicated load/save patterns across UI pages.
"""

import json
import sqlite3

from slidebuddy.db.models import Version
from slidebuddy.db.queries import create_version, get_versions_for_project


def load_versioned_states(
    conn: sqlite3.Connection,
    project_id: str,
    prefix: str,
) -> dict[int, list | dict]:
    """Load all versioned JSON states matching a prefix.

    Returns {chapter_index: parsed_json} for all versions whose
    ``state`` starts with *prefix*.
    """
    result: dict[int, list | dict] = {}
    versions = get_versions_for_project(conn, project_id)
    for v in versions:
        if v.state and v.state.startswith(prefix) and v.state_json:
            try:
                idx = int(v.state.split("_")[-1])
                result[idx] = json.loads(v.state_json)
            except (ValueError, json.JSONDecodeError):
                pass
    return result


def save_versioned_state(
    conn: sqlite3.Connection,
    project_id: str,
    state_label: str,
    chapter_index: int,
    data: list | dict,
) -> None:
    """Persist a JSON state blob under a version label.

    Replaces any existing version with the same project_id + state_label.
    """
    conn.execute(
        "DELETE FROM versions WHERE project_id = ? AND state = ?",
        (project_id, state_label),
    )
    conn.commit()
    if data:
        create_version(conn, Version(
            project_id=project_id,
            chapter_index=chapter_index,
            version_number=1,
            state=state_label,
            state_json=json.dumps(data, ensure_ascii=False),
        ))
