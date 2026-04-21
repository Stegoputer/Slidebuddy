"""Chapter planning endpoints."""

import json
import logging
import re

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


def _parse_user_slide_count(feedback: str | None) -> int | None:
    """Extract an explicitly requested total slide count from the user feedback string.

    The modal sends ``GEWÜNSCHTE FOLIENANZAHL: <n>`` when the user fills in the
    slide-count field.  Returns None if not present or not a positive integer.
    """
    if not feedback:
        return None
    m = re.search(r"GEWÜNSCHTE\s+FOLIENANZAHL:\s*(\d+)", feedback, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        return n if n > 0 else None
    return None


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

    # Respect user's explicit slide count — this is the TOTAL desired slide count
    # for the entire presentation.  Always override density so the LLM receives
    # the correct total target, regardless of whether it is above or below the
    # text-volume-based estimate.
    user_slide_count = _parse_user_slide_count(body.feedback if body else None)
    if user_slide_count:
        density["max_total_slides"] = user_slide_count
        # Recalculate suggested chapters based on the user's desired total
        target_per_ch = density["target_slides_per_chapter"]
        density["suggested_chapters"] = max(
            2,
            min(density["max_chapters"], user_slide_count // max(1, target_per_ch)),
        )
        logger.info(
            "User requested %d slides total — density updated: max_total=%d, "
            "suggested_chapters=%d",
            user_slide_count, density["max_total_slides"], density["suggested_chapters"],
        )

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
        from slidebuddy.core.chapter_planning import _source_title as _st
        source_summaries = [
            f"{_st(s)} [{s.source_type}]" + (f": {s.original_text[:300]}..." if s.original_text else "")
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
                density=density,
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

    # Post-process: scale to user's requested total, or enforce density cap
    chapters_data = result.get("chapters", [])
    total_estimated = sum(c.get("estimated_slide_count", 0) for c in chapters_data)
    min_per_ch = density["min_slides_per_chapter"]
    if user_slide_count and total_estimated > 0 and total_estimated != user_slide_count:
        # User specified a slide count — scale all chapters proportionally.
        # Use remainder-aware distribution so the total is exact.
        ratio = user_slide_count / total_estimated
        raw = [max(min_per_ch, int(c["estimated_slide_count"] * ratio)) for c in chapters_data]
        remainder = user_slide_count - sum(raw)
        for i in range(abs(remainder)):
            if remainder > 0:
                raw[i % len(raw)] += 1
            elif raw[i % len(raw)] > min_per_ch:
                raw[i % len(raw)] -= 1
        for i, c in enumerate(chapters_data):
            c["estimated_slide_count"] = raw[i]
        logger.info(
            "Scaled total slides from %d to user-requested %d",
            total_estimated,
            sum(c["estimated_slide_count"] for c in chapters_data),
        )
    elif not user_slide_count and total_estimated > density["max_total_slides"]:
        target = density["max_total_slides"]
        ratio = target / total_estimated
        raw = [max(min_per_ch, int(c["estimated_slide_count"] * ratio)) for c in chapters_data]
        remainder = target - sum(raw)
        for i in range(abs(remainder)):
            if remainder > 0:
                raw[i % len(raw)] += 1
            elif raw[i % len(raw)] > min_per_ch:
                raw[i % len(raw)] -= 1
        for i, c in enumerate(chapters_data):
            c["estimated_slide_count"] = raw[i]
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
        delete_steps_after(conn, project_id, "sources")

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
