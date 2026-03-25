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
    status TEXT DEFAULT 'planned'
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


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
