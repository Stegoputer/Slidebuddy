"""Section planning endpoints."""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException

from slidebuddy.core.section_planning import plan_chapter_slides
from slidebuddy.core.progress import delete_steps_after
from slidebuddy.db.queries import (
    get_all_section_plans,
    get_chapters_for_project,
    get_project,
    get_section_plan,
    save_section_plan,
)

from ..dependencies import _llm_http_exception, get_db
from ..schemas import SectionPlanOut, SectionPlanUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


def _strip_planning_directives(feedback: str | None) -> str | None:
    """Remove slide-count directive from planning feedback before section planning.

    The total slide count (GEWÜNSCHTE FOLIENANZAHL: N) is a chapter-planning
    directive already encoded in each chapter's estimated_slide_count. Passing
    it to section planning causes the LLM to misinterpret the total as a
    per-chapter target.
    """
    if not feedback:
        return feedback
    lines = [
        line for line in feedback.splitlines()
        if not re.search(r"GEWÜNSCHTE\s+FOLIENANZAHL:", line, re.IGNORECASE)
    ]
    return "\n".join(lines).strip() or None


@router.get("/{project_id}/sections", response_model=list[SectionPlanOut])
def list_sections(project_id: str, conn=Depends(get_db)):
    states = get_all_section_plans(conn, project_id)
    results = []
    for idx, data in sorted(states.items()):
        if isinstance(data, dict) and "slides" in data:
            slide_list = data["slides"]
        elif isinstance(data, list):
            slide_list = data
        else:
            logger.warning("Unexpected section data format for chapter %d: %s", idx, type(data).__name__)
            slide_list = []
        slide_list = [s for s in slide_list if isinstance(s, dict)]
        results.append(SectionPlanOut(chapter_index=idx, slides=slide_list))
    return results


@router.post("/{project_id}/sections/plan", response_model=list[SectionPlanOut])
def plan(project_id: str, conn=Depends(get_db)):
    """Generate section plans for all chapters."""
    project = get_project(conn, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    chapters = get_chapters_for_project(conn, project_id)
    if not chapters:
        raise HTTPException(400, "No chapters planned yet")

    # Build per-chapter work items (no DB access inside the worker — threads
    # can't safely share sqlite connections, and we want pure LLM work there)
    def _prepare(chapter) -> tuple[int, dict, list[str]]:
        chapter_dict = {
            "title": chapter.title or "",
            "summary": chapter.summary or "",
            "estimated_slide_count": chapter.estimated_slide_count or 5,
            "key_topics": [],
        }
        chapter_source_ids: list[str] = []
        try:
            chapter_source_ids = json.loads(chapter.source_ids) if chapter.source_ids else []
        except (json.JSONDecodeError, TypeError):
            pass
        return chapter.chapter_index, chapter_dict, chapter_source_ids

    work_items = [(ch, _prepare(ch)) for ch in chapters]

    def _run_one(prepared):
        idx, chapter_dict, chapter_source_ids = prepared
        logger.info(
            "Section planning ch=%d sources=%d",
            idx, len(chapter_source_ids),
        )
        return plan_chapter_slides(
            project_id=project_id,
            chapter=chapter_dict,
            language=project.language,
            project_override=project.parsed_override,
            source_ids=chapter_source_ids,
            user_feedback=_strip_planning_directives(project.planning_prompt),
        )

    # Parallelisierung: LLM-Calls sind I/O-bound, ThreadPoolExecutor reicht.
    # max_workers=4 deckt die meisten Projekte (4-8 Kapitel) ab und hält die
    # Rate bei Claude/OpenAI im grünen Bereich.
    plan_results: dict[int, dict] = {}
    errors: list[dict] = []

    # Hard ceiling per chapter so a single hung LLM call cannot block the
    # whole request indefinitely. The LLM SDK has its own timeout (120s per
    # call, see llm/router.py); this is the outer wall-clock guard for the
    # full chapter slot including retries.
    PER_CHAPTER_TIMEOUT_SECONDS = 600

    with ThreadPoolExecutor(max_workers=min(4, len(work_items) or 1)) as executor:
        future_map = {
            executor.submit(_run_one, prepared): chapter
            for chapter, prepared in work_items
        }
        try:
            for future in as_completed(future_map, timeout=PER_CHAPTER_TIMEOUT_SECONDS * len(work_items)):
                chapter = future_map[future]
                try:
                    plan_results[chapter.chapter_index] = future.result(timeout=PER_CHAPTER_TIMEOUT_SECONDS)
                except Exception as e:
                    logger.error(
                        "Section planning failed for chapter %d: %s",
                        chapter.chapter_index, e, exc_info=True,
                    )
                    errors.append({
                        "chapter_index": chapter.chapter_index,
                        "title": chapter.title,
                        "error": str(e),
                    })
        except TimeoutError as e:
            unfinished = [
                future_map[f].chapter_index for f in future_map if not f.done()
            ]
            logger.error("Section planning hit overall timeout — unfinished chapters: %s", unfinished)
            for f in future_map:
                if not f.done():
                    f.cancel()
            for idx in unfinished:
                errors.append({
                    "chapter_index": idx,
                    "title": "",
                    "error": f"Timeout nach {PER_CHAPTER_TIMEOUT_SECONDS}s pro Kapitel",
                })

    # DB-Writes sequentiell im Main-Thread (sqlite ist nicht thread-safe)
    results = []
    for chapter in chapters:
        result = plan_results.get(chapter.chapter_index)
        if result is None:
            continue
        save_section_plan(conn, project_id, chapter.chapter_index, result)
        slides = result.get("slides", []) if isinstance(result, dict) else result
        results.append(SectionPlanOut(
            chapter_index=chapter.chapter_index,
            slides=slides,
        ))

    if errors and not results:
        # Alle Kapitel gescheitert → echter 500 mit aggregierter Info
        first = errors[0]
        raise _llm_http_exception(
            Exception(first["error"]),
            f"Sektionsplanung komplett fehlgeschlagen (Kapitel {first['chapter_index']})",
        )

    if errors:
        logger.warning(
            "Section planning partially failed: %d/%d chapters ok, failed: %s",
            len(results), len(chapters),
            [e["chapter_index"] for e in errors],
        )

    return results


@router.put("/{project_id}/sections/{chapter_index}", response_model=SectionPlanOut)
def update_section(project_id: str, chapter_index: int, body: SectionPlanUpdate, conn=Depends(get_db)):
    """Save an edited slide plan for a single chapter, preserving reasoning and other metadata."""
    existing = get_section_plan(conn, project_id, chapter_index) or {}

    # Preserve any top-level metadata (e.g. "reasoning") that the LLM produced
    updated = {
        **({k: v for k, v in existing.items() if k != "slides"} if isinstance(existing, dict) else {}),
        "slides": [s.model_dump(exclude_none=True) for s in body.slides],
    }

    save_section_plan(conn, project_id, chapter_index, updated)
    return SectionPlanOut(chapter_index=chapter_index, slides=updated["slides"])


@router.delete("/{project_id}/sections", status_code=204)
def reset_sections(project_id: str, conn=Depends(get_db)):
    """Delete all section plans and downstream data."""
    delete_steps_after(conn, project_id, "chapters")
