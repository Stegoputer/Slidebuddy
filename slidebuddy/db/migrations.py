import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    topic TEXT,
    language TEXT DEFAULT 'de',
    prompt_override TEXT,
    global_text_length TEXT DEFAULT 'medium',
    llm_config TEXT,
    planning_prompt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS versions (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    chapter_index INTEGER,
    version_number INTEGER,
    state TEXT DEFAULT 'draft',
    state_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    version_id TEXT REFERENCES versions(id),
    chapter_index INTEGER,
    title TEXT,
    summary TEXT,
    estimated_slide_count INTEGER,
    status TEXT DEFAULT 'planned',
    source_ids TEXT DEFAULT '',
    source_segment TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS slides (
    id TEXT PRIMARY KEY,
    chapter_id TEXT REFERENCES chapters(id),
    project_id TEXT REFERENCES projects(id),
    slide_index INTEGER,
    slide_index_in_chapter INTEGER,
    template_type TEXT,
    title TEXT,
    subtitle TEXT,
    content_json TEXT,
    speaker_notes TEXT,
    chain_of_thought TEXT,
    is_reused BOOLEAN DEFAULT FALSE,
    source_slide_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    source_type TEXT,
    filename TEXT,
    original_text TEXT,
    chunk_count INTEGER DEFAULT 0,
    processing_status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_gaps (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    chapter_id TEXT REFERENCES chapters(id),
    description TEXT,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS slide_masters (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS section_plans (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    chapter_index INTEGER NOT NULL,
    slides_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, chapter_index)
);

CREATE TABLE IF NOT EXISTS master_templates (
    id TEXT PRIMARY KEY,
    master_id TEXT REFERENCES slide_masters(id) ON DELETE CASCADE,
    layout_index INTEGER NOT NULL,
    layout_name TEXT NOT NULL,
    template_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,
    placeholder_schema TEXT,
    content_schema TEXT,
    generation_prompt TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    _run_migrations(conn)
    conn.close()


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run incremental schema migrations for existing databases."""
    # Rename langgraph_state → state_json (cleanup of legacy LangGraph naming)
    cursor = conn.execute("PRAGMA table_info(versions)")
    columns = [row[1] for row in cursor.fetchall()]
    if "langgraph_state" in columns and "state_json" not in columns:
        conn.execute("ALTER TABLE versions RENAME COLUMN langgraph_state TO state_json")
        conn.commit()

    # Add source_ids column to chapters table
    cursor = conn.execute("PRAGMA table_info(chapters)")
    chapter_cols = [row[1] for row in cursor.fetchall()]
    if "source_ids" not in chapter_cols:
        conn.execute("ALTER TABLE chapters ADD COLUMN source_ids TEXT DEFAULT ''")
        conn.commit()

    if "source_segment" not in chapter_cols:
        conn.execute("ALTER TABLE chapters ADD COLUMN source_segment TEXT DEFAULT NULL")
        conn.commit()

    # Add planning_prompt column to projects table
    cursor = conn.execute("PRAGMA table_info(projects)")
    project_cols = [row[1] for row in cursor.fetchall()]
    if "planning_prompt" not in project_cols:
        conn.execute("ALTER TABLE projects ADD COLUMN planning_prompt TEXT")
        conn.commit()

    # Migrate section plans from versions table → section_plans table
    _migrate_section_plans(conn)


def _migrate_section_plans(conn: sqlite3.Connection) -> None:
    """One-time migration: copy section_plan_* rows from versions into section_plans."""
    import json
    import uuid

    rows = conn.execute(
        "SELECT project_id, state, state_json FROM versions WHERE state LIKE 'section_plan_%'"
    ).fetchall()
    if not rows:
        return

    migrated = 0
    for row in rows:
        try:
            chapter_index = int(row[1].split("_")[-1])
            slides_json = row[2]
            if not slides_json or not slides_json.strip():
                continue
            # Validate JSON before inserting
            json.loads(slides_json)
            conn.execute(
                """INSERT OR IGNORE INTO section_plans
                   (id, project_id, chapter_index, slides_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (str(uuid.uuid4()), row[0], chapter_index, slides_json),
            )
            migrated += 1
        except (ValueError, TypeError):
            pass  # Skip malformed rows

    if migrated:
        conn.execute(
            "DELETE FROM versions WHERE state LIKE 'section_plan_%'"
        )
        conn.commit()


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
