import sqlite3
from typing import List, Optional

from slidebuddy.db.models import MasterTemplate, SlideMaster
from ._base import _parse_datetime


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
               generation_prompt = ?, is_active = ?, template_key = ?,
               placeholder_schema = ?
           WHERE id = ?""",
        (tpl.display_name, tpl.description, tpl.content_schema,
         tpl.generation_prompt, tpl.is_active, tpl.template_key,
         tpl.placeholder_schema, tpl.id),
    )
    conn.commit()
    return tpl


# ---------------------------------------------------------------------------
# Helpers for template type resolution (used by config and generation)
# ---------------------------------------------------------------------------

def get_available_template_types(conn: sqlite3.Connection) -> list[str]:
    """Return template_keys from the active master, or None if no master is set."""
    templates = get_active_master_templates(conn)
    if templates:
        return [t.template_key for t in templates if t.is_active]
    return []


def get_template_labels(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {template_key: display_name} from the active master, or {} if none."""
    templates = get_active_master_templates(conn)
    if templates:
        return {t.template_key: t.display_name for t in templates if t.is_active}
    return {}
