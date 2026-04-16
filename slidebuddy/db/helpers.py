"""Shared database helper functions for version state persistence.

Eliminates duplicated load/save patterns across UI pages.
"""

import json
import logging
import sqlite3

from slidebuddy.db.models import Version
from slidebuddy.db.queries import create_version, get_versions_for_project

logger = logging.getLogger(__name__)


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
        if not v.state or not v.state.startswith(prefix):
            continue
        # Skip empty or None JSON
        if not v.state_json or not v.state_json.strip():
            logger.warning(
                "Skipping version %s for project %s: empty state_json",
                v.state, project_id,
            )
            continue
        try:
            idx = int(v.state.split("_")[-1])
            parsed = json.loads(v.state_json)
            # Only accept dicts and lists
            if isinstance(parsed, (dict, list)):
                result[idx] = parsed
            else:
                logger.warning(
                    "Skipping version %s for project %s: unexpected type %s",
                    v.state, project_id, type(parsed).__name__,
                )
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(
                "Skipping corrupt versioned state %s for project %s: %s",
                v.state, project_id, e,
            )
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
