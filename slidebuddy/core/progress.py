"""Project progress detection — determines which workflow step a project is at.

The workflow has 4 steps:
  1. sources    — Upload and process sources
  2. chapters   — Plan chapter structure
  3. sections   — Plan slides per chapter
  4. generation — Generate slide content

Progress is determined from the database, not session state, so it
survives page navigation and browser refresh.
"""

import sqlite3

from slidebuddy.db.queries import (
    get_chapters_for_project,
    get_slides_for_project,
    get_sources_for_project,
    get_versions_for_project,
)

# Ordered workflow steps — each maps to a current_page value
WORKFLOW_STEPS = [
    ("sources", "projects"),
    ("chapters", "chapter_planning"),
    ("sections", "section_planning"),
    ("generation", "slide_generation"),
]

STEP_LABELS = {
    "sources": "Quellen",
    "chapters": "Kapitelplanung",
    "sections": "Sektionsplanung",
    "generation": "Generierung",
}


def detect_project_step(conn: sqlite3.Connection, project_id: str) -> str:
    """Detect which workflow step a project has reached.

    Returns the step name (sources/chapters/sections/generation).
    Logic: work backwards from the latest step — if slides exist, we're at
    generation; if section plans exist, we're at sections; etc.
    """
    # Check for generated slides
    slides = get_slides_for_project(conn, project_id)
    if slides:
        return "generation"

    # Check for in-progress generation (draft slides in versions)
    versions = get_versions_for_project(conn, project_id)
    has_gen_draft = any(v.state and v.state.startswith("gen_slides_") for v in versions)
    if has_gen_draft:
        return "generation"

    # Check for section plans
    has_sections = any(
        v.state and v.state.startswith("section_plan_") for v in versions
    )
    if has_sections:
        return "sections"

    # Check for chapters
    chapters = get_chapters_for_project(conn, project_id)
    if chapters:
        return "chapters"

    # Default: sources step
    return "sources"


def get_page_for_step(step: str) -> str:
    """Map a workflow step name to its current_page value."""
    for step_name, page in WORKFLOW_STEPS:
        if step_name == step:
            return page
    return "projects"


def get_step_index(step: str) -> int:
    """Get the 0-based index of a step in the workflow."""
    for i, (step_name, _) in enumerate(WORKFLOW_STEPS):
        if step_name == step:
            return i
    return 0


def get_steps_after(step: str) -> list[str]:
    """Get all step names that come AFTER the given step."""
    idx = get_step_index(step)
    return [name for name, _ in WORKFLOW_STEPS[idx + 1:]]


def delete_steps_after(conn: sqlite3.Connection, project_id: str, keep_step: str):
    """Delete all data for steps that come after keep_step.

    Example: if keep_step="chapters", deletes section plans, slides, gen drafts.
    """
    steps_to_delete = get_steps_after(keep_step)

    for step in steps_to_delete:
        if step == "generation":
            # Delete slides and generation drafts
            conn.execute("DELETE FROM slides WHERE project_id = ?", (project_id,))
            conn.execute(
                "DELETE FROM versions WHERE project_id = ? AND state LIKE 'gen_slides_%'",
                (project_id,),
            )
            conn.execute(
                "DELETE FROM versions WHERE project_id = ? AND state = 'reviewed'",
                (project_id,),
            )
            # Reset chapter status back to planned
            conn.execute(
                "UPDATE chapters SET status = 'planned' WHERE project_id = ?",
                (project_id,),
            )

        elif step == "sections":
            # Delete section plans
            conn.execute(
                "DELETE FROM versions WHERE project_id = ? AND state LIKE 'section_plan_%'",
                (project_id,),
            )

        elif step == "chapters":
            # Delete chapters, source gaps, and chapter plan version
            conn.execute("DELETE FROM source_gaps WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM chapters WHERE project_id = ?", (project_id,))
            conn.execute(
                "DELETE FROM versions WHERE project_id = ? AND state = 'chapter_plan'",
                (project_id,),
            )

    conn.commit()
