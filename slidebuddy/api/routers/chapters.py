"""Chapter planning endpoints."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from slidebuddy.config.defaults import load_preferences
from slidebuddy.core.chapter_planning import (
    compute_density_params,
    plan_chapters,
    plan_chapters_full_source_split,
    plan_chapters_one_per_source,
)
from slidebuddy.core.progress import delete_steps_after
from slidebuddy.db.helpers import save_versioned_state
from slidebuddy.db.models import Chapter
from slidebuddy.db.queries import (
    create_chapter,
    create_source_gap,
    get_chapters_for_project,
    get_project,
    get_source_gaps_for_project,
    get_sources_for_project,
    update_project,
)
from slidebuddy.db.models import SourceGap

from ..dependencies import _llm_http_exception, get_db
from ..schemas import ChapterBulkUpdate, ChapterOut, ChapterPlanRequest, SourceGapOut

logger = logging.getLogger(__name__)
router = APIRouter()


def _chapter_to_out(c: Chapter) -> ChapterOut:
    try:
        source_ids = json.loads(c.source_ids) if c.source_ids else []
    except (json.JSONDecodeError, TypeError):
        source_ids = []
    return ChapterOut(
        id=c.id, project_id=c.project_id, chapter_index=c.chapter_index,
        title=c.title or "", summary=c.summary or "",
        estimated_slide_count=c.estimated_slide_count or 0,
        status=c.status or "planned",
        source_ids=source_ids,
    )


@router.get("/{project_id}/chapters", response_model=list[ChapterOut])
def list_chapters(project_id: str, conn=Depends(get_db)):
    return [_chapter_to_out(c) for c in get_chapters_for_project(conn, project_id)]


@router.post("/{project_id}/chapters/plan", response_model=list[ChapterOut])
def plan(project_id: str, body: ChapterPlanRequest = None, conn=Depends(get_db)):
    """Generate chapter plan and save to DB with status 'planned'.

    Two strategies:
      - "auto" (default): LLM-based chapter planning.
      - "one_per_source": Deterministic — one chapter per uploaded source,
        no LLM call, no 500 risk from API failures.
    """
    project = get_project(conn, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    sources = get_sources_for_project(conn, project_id)
    if not sources:
        raise HTTPException(400, "No sources uploaded yet")

    strategy = (body.strategy if body else None) or "auto"

    # Compute density params from source text volume + settings
    total_chars = sum(len(s.original_text or "") for s in sources)
    planning_prefs = load_preferences().get("planning", {})
    density = compute_density_params(total_chars, planning_prefs)

    if strategy == "one_per_source":
        result = plan_chapters_one_per_source(sources)
    elif strategy == "full_source_split":
        try:
            result = plan_chapters_full_source_split(
                sources,
                user_feedback=body.feedback if body else None,
                language=project.language,
                project_override=project.parsed_override,
                density=density,
            )
        except Exception as e:
            error_type = type(e).__name__
            logger.error("Full-source chapter planning failed (%s): %s", error_type, e, exc_info=True)
            raise _llm_http_exception(e, "Kapitelplanung (Quellen aufteilen)")
    else:
        source_summaries = [
            f"{s.filename} [{s.source_type}]" + (f": {s.original_text[:300]}..." if s.original_text else "")
            for s in sources
        ]
        try:
            result = plan_chapters(
                project_id=project_id,
                topic=project.topic or project.name,
                language=project.language,
                source_summaries=source_summaries,
                project_override=project.parsed_override,
                user_feedback=body.feedback if body else None,
            )
        except Exception as e:
            error_type = type(e).__name__
            logger.error("Chapter planning LLM failed (%s): %s", error_type, e, exc_info=True)
            raise _llm_http_exception(e, "Kapitelplanung")

    # Persist user's planning prompt for downstream section planning
    planning_feedback = (body.feedback if body else None) or None
    if planning_feedback:
        project.planning_prompt = planning_feedback
        update_project(conn, project)

    # Post-process: enforce max_total_slides from density settings
    chapters_data = result.get("chapters", [])
    total_estimated = sum(c.get("estimated_slide_count", 0) for c in chapters_data)
    if total_estimated > density["max_total_slides"]:
        ratio = density["max_total_slides"] / total_estimated
        min_per_ch = density["min_slides_per_chapter"]
        for c in chapters_data:
            c["estimated_slide_count"] = max(
                min_per_ch,
                round(c["estimated_slide_count"] * ratio),
            )
        logger.info(
            "Capped total slides from %d to %d (max_total_slides=%d)",
            total_estimated,
            sum(c["estimated_slide_count"] for c in chapters_data),
            density["max_total_slides"],
        )

    # Common DB-save path for all strategies
    try:
        delete_steps_after(conn, project_id, "sources")

        # Map LLM-returned source filenames to DB source IDs
        filename_to_id = {s.filename: s.id for s in sources}
        created = []
        for i, ch_data in enumerate(chapters_data):
            # Resolve source IDs: prefer _source_id (one_per_source/full_source_split), then source_filenames (auto LLM)
            if ch_data.get("_source_id"):
                resolved_ids = [ch_data["_source_id"]]
            else:
                filenames = ch_data.get("source_filenames", [])
                resolved_ids = [filename_to_id[fn] for fn in filenames if fn in filename_to_id]

            # Persist source_segment for full_source_split chapters
            source_segment_raw = ch_data.get("_source_segment")

            chapter = Chapter(
                project_id=project_id,
                chapter_index=i,
                title=ch_data.get("title", ""),
                summary=ch_data.get("summary", ""),
                estimated_slide_count=ch_data.get("estimated_slide_count", 0),
                status="planned",
                source_ids=json.dumps(resolved_ids) if resolved_ids else "",
                source_segment=json.dumps(source_segment_raw) if source_segment_raw else None,
            )
            create_chapter(conn, chapter)
            created.append(_chapter_to_out(chapter))

        source_gaps = result.get("source_gaps", [])
        conn.execute("DELETE FROM source_gaps WHERE project_id = ?", (project_id,))
        conn.commit()

        title_to_id = {c.title: c.id for c in created}
        for gap_data in source_gaps:
            chapter_title = gap_data.get("chapter_title", "")
            gap = SourceGap(
                project_id=project_id,
                chapter_id=title_to_id.get(chapter_title),
                description=gap_data.get("description", ""),
                status=gap_data.get("severity", "medium"),
            )
            create_source_gap(conn, gap)

        save_versioned_state(conn, project_id, "chapter_plan", 0, result)
        return created

    except Exception as e:
        logger.error("Chapter DB save failed: %s", e, exc_info=True)
        conn.rollback()
        raise HTTPException(500, f"Saving chapters failed: {e}")


@router.post("/{project_id}/chapters/approve", response_model=list[ChapterOut])
def approve(project_id: str, body: ChapterBulkUpdate = None, conn=Depends(get_db)):
    """Approve the current chapter plan.

    Two modes:
      1. No body → flip all existing 'planned' chapters to 'approved'.
      2. Body with chapters → replace chapters with provided data (all approved).
    """
    project = get_project(conn, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if body and body.chapters:
        # Mode 2: Replace chapters with user-edited data
        delete_steps_after(conn, project_id, "sources")

        created = []
        for i, ch_data in enumerate(body.chapters):
            chapter = Chapter(
                project_id=project_id,
                chapter_index=i,
                title=ch_data.title,
                summary=ch_data.summary,
                estimated_slide_count=ch_data.estimated_slide_count,
                status="approved",
                source_ids=json.dumps(ch_data.source_ids) if ch_data.source_ids else "",
            )
            create_chapter(conn, chapter)
            created.append(_chapter_to_out(chapter))

        save_versioned_state(
            conn, project_id, "chapter_plan", 0,
            [c.model_dump() for c in body.chapters],
        )
        return created

    # Mode 1: Approve existing planned chapters in-place
    existing = get_chapters_for_project(conn, project_id)
    if not existing:
        raise HTTPException(400, "No chapters to approve — run /plan first")

    conn.execute(
        "UPDATE chapters SET status = 'approved' WHERE project_id = ?",
        (project_id,),
    )
    conn.commit()

    return [_chapter_to_out(c) for c in get_chapters_for_project(conn, project_id)]


@router.get("/{project_id}/chapters/gaps", response_model=list[SourceGapOut])
def list_source_gaps(project_id: str, conn=Depends(get_db)):
    """Return source gap analysis results from chapter planning."""
    gaps = get_source_gaps_for_project(conn, project_id)
    return [
        SourceGapOut(
            id=g.id,
            project_id=g.project_id,
            chapter_id=g.chapter_id,
            description=g.description,
            severity=g.status,  # stored in status field
        )
        for g in gaps
    ]


@router.put("/{project_id}/chapters", response_model=list[ChapterOut])
def update_chapters(project_id: str, body: ChapterBulkUpdate, conn=Depends(get_db)):
    """Bulk update chapters (reorder, edit)."""
    try:
        conn.execute("DELETE FROM chapters WHERE project_id = ?", (project_id,))

        created = []
        for i, ch_data in enumerate(body.chapters):
            chapter = Chapter(
                id=ch_data.id,
                project_id=project_id,
                chapter_index=i,
                title=ch_data.title or "",
                summary=ch_data.summary or "",
                estimated_slide_count=ch_data.estimated_slide_count or 0,
                status=ch_data.status or "planned",
                source_ids=json.dumps(ch_data.source_ids) if ch_data.source_ids else "",
            )
            create_chapter(conn, chapter)
            created.append(_chapter_to_out(chapter))

        conn.commit()
        return created
    except Exception:
        conn.rollback()
        raise
