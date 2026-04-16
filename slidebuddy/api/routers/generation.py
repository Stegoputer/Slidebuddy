"""Slide generation endpoints — single, batch, and WebSocket progress."""

import asyncio
import json
import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from slidebuddy.config.defaults import load_preferences
from slidebuddy.core.slide_generation import generate_slide, generate_slides_batch
from slidebuddy.db.helpers import load_versioned_states, save_versioned_state
from slidebuddy.db.models import Slide as SlideModel
from slidebuddy.db.queries import (
    create_slide,
    get_all_section_plans,
    get_chapters_for_project,
    get_project,
    get_section_plan,
)

from ..dependencies import _llm_http_exception, get_db
from ..schemas import BatchStartRequest, BatchStatusOut, GenerateChapterRequest

logger = logging.getLogger(__name__)
router = APIRouter()


# In-memory batch status per project
_batch_jobs: dict[str, BatchStatusOut] = {}


def _extract_slide_plans(section_data: dict | list | None) -> list[dict]:
    """Normalize section plan data into a flat list of slide plan dicts."""
    if isinstance(section_data, dict) and "slides" in section_data:
        return section_data["slides"]
    if isinstance(section_data, list):
        return section_data
    return []


def _result_to_slide(
    result: dict,
    project_id: str,
    chapter_id: str,
    slide_index: int,
    slide_index_in_chapter: int,
    slide_plan: dict,
) -> SlideModel:
    """Convert an LLM generation result dict to a Slide DB model."""
    content = result.get("content")
    return SlideModel(
        project_id=project_id,
        chapter_id=chapter_id,
        slide_index=slide_index,
        slide_index_in_chapter=slide_index_in_chapter,
        template_type=slide_plan.get("template_type", "content"),
        title=result.get("title", ""),
        subtitle=result.get("subtitle"),
        content_json=json.dumps(content) if content else None,
        speaker_notes=result.get("speaker_notes"),
        chain_of_thought=result.get("chain_of_thought"),
    )


@router.get("/{project_id}/generate/status")
def get_status(project_id: str, conn=Depends(get_db)):
    """Get current generation state — drafted slides per chapter."""
    states = load_versioned_states(conn, project_id, "gen_slides_")
    summary = {
        str(idx): len(slides) if isinstance(slides, list) else 0
        for idx, slides in states.items()
    }
    job = _batch_jobs.get(project_id)
    return {
        "drafted_slides": summary,
        "batch": job.model_dump() if job else None,
    }


@router.post("/{project_id}/generate/single")
def generate_single(
    project_id: str,
    body: BatchStartRequest,
    conn=Depends(get_db),
):
    """Generate a single slide."""
    project = get_project(conn, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    chapters = get_chapters_for_project(conn, project_id)
    if body.chapter_index >= len(chapters):
        raise HTTPException(400, "Invalid chapter index")

    chapter = chapters[body.chapter_index]
    slide_plans = _extract_slide_plans(get_section_plan(conn, project_id, body.chapter_index))
    if not slide_plans:
        raise HTTPException(400, "No section plans for this chapter")

    # Load existing generated slides
    gen_states = load_versioned_states(conn, project_id, "gen_slides_")
    existing = gen_states.get(body.chapter_index, [])

    # Use requested slide index if provided, otherwise generate next in sequence
    target_idx = body.slide_index_in_chapter if body.slide_index_in_chapter is not None else len(existing)

    if target_idx >= len(slide_plans):
        return {"status": "complete", "slides": existing}

    text_length = body.text_length or project.global_text_length or "medium"
    chapter_context = {
        "title": chapter.title,
        "summary": chapter.summary,
        "chapter_index": body.chapter_index,
        "planning_prompt": project.planning_prompt,
    }

    result = generate_slide(
        project_id=project_id,
        slide_plan=slide_plans[target_idx],
        chapter_context=chapter_context,
        language=project.language,
        text_length=text_length,
        slide_index=target_idx + 1,
        total_slides_in_chapter=len(slide_plans),
        project_override=project.parsed_override,
    )

    # Update versioned state (insert or replace at target position)
    if target_idx < len(existing):
        existing[target_idx] = result
    else:
        existing.append(result)
    save_versioned_state(
        conn, project_id,
        f"gen_slides_{body.chapter_index}",
        body.chapter_index,
        existing,
    )

    # Compute global slide index for SQL table
    global_offset = sum(len(gen_states.get(i, [])) for i in range(body.chapter_index))

    # Upsert: delete existing slide at this position, then insert fresh
    conn.execute(
        "DELETE FROM slides WHERE project_id=? AND chapter_id=? AND slide_index_in_chapter=?",
        (project_id, chapter.id, target_idx),
    )
    create_slide(conn, _result_to_slide(
        result, project_id, chapter.id,
        slide_index=global_offset + target_idx,
        slide_index_in_chapter=target_idx,
        slide_plan=slide_plans[target_idx],
    ))

    return {"status": "ok", "slide": result, "total": len(existing)}


@router.post("/{project_id}/generate/chapter")
def generate_chapter(project_id: str, body: GenerateChapterRequest, conn=Depends(get_db)):
    """Generate all slides for one chapter using batch LLM calls.

    Batch size controls how many slide plans are sent to the LLM in a single call.
    Falls back to the 'batch_size' preference (default 4) when not specified.
    Clears any previously generated slides for the chapter before generating.
    """
    project = get_project(conn, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    chapters = get_chapters_for_project(conn, project_id)
    if body.chapter_index >= len(chapters):
        raise HTTPException(400, "Invalid chapter index")

    chapter = chapters[body.chapter_index]
    slide_plans = _extract_slide_plans(get_section_plan(conn, project_id, body.chapter_index))
    if not slide_plans:
        raise HTTPException(400, "No section plans for this chapter")

    # Clear existing data for this chapter (clean re-generation)
    conn.execute("DELETE FROM slides WHERE project_id=? AND chapter_id=?", (project_id, chapter.id))
    conn.execute(
        "DELETE FROM versions WHERE project_id=? AND state=?",
        (project_id, f"gen_slides_{body.chapter_index}"),
    )
    conn.commit()

    prefs = load_preferences()
    batch_size = body.batch_size or prefs.get("batch_size", 4)
    text_length = body.text_length or project.global_text_length or "medium"
    chapter_context = {
        "title": chapter.title,
        "summary": chapter.summary,
        "chapter_index": body.chapter_index,
        "planning_prompt": project.planning_prompt,
    }

    try:
        results = generate_slides_batch(
            project_id=project_id,
            slide_plans=slide_plans,
            chapter_context=chapter_context,
            language=project.language,
            text_length=text_length,
            project_override=project.parsed_override,
            batch_size=batch_size,
        )
    except Exception as e:
        logger.error("Batch generation failed for chapter %d: %s", body.chapter_index, e, exc_info=True)
        raise _llm_http_exception(e, f"Folien-Generierung Kapitel {body.chapter_index}")

    # Save to versioned state
    save_versioned_state(
        conn, project_id,
        f"gen_slides_{body.chapter_index}",
        body.chapter_index,
        results,
    )

    # Compute global offset: sum slides from all previous chapters
    gen_states = load_versioned_states(conn, project_id, "gen_slides_")
    global_offset = sum(len(gen_states.get(i, [])) for i in range(body.chapter_index))

    # Save all slides to SQL table
    for idx, result in enumerate(results):
        create_slide(conn, _result_to_slide(
            result, project_id, chapter.id,
            slide_index=global_offset + idx,
            slide_index_in_chapter=idx,
            slide_plan=slide_plans[idx],
        ))

    return {"status": "ok", "total": len(results)}


@router.websocket("/ws/generation/{project_id}")
async def generation_ws(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time batch generation progress."""
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    try:
        # Wait for start command
        data = await websocket.receive_json()
        if data.get("action") != "start_batch":
            await websocket.send_json({"type": "error", "message": "Expected start_batch action"})
            return

        chapter_index = data.get("chapter_index", 0)
        text_length = data.get("text_length", "medium")

        # Get project data (sync DB access in executor)
        def _load_context():
            from slidebuddy.config.defaults import DB_PATH
            from slidebuddy.db.migrations import get_connection
            conn = get_connection(DB_PATH)
            project = get_project(conn, project_id)
            chapters = get_chapters_for_project(conn, project_id)
            section_data = get_section_plan(conn, project_id, chapter_index)
            gen_states = load_versioned_states(conn, project_id, "gen_slides_")
            conn.close()
            return project, chapters, section_data, gen_states

        project, chapters, section_data, gen_states = await loop.run_in_executor(None, _load_context)

        if not project or chapter_index >= len(chapters):
            await websocket.send_json({"type": "error", "message": "Invalid project or chapter"})
            return

        chapter = chapters[chapter_index]
        slide_plans = _extract_slide_plans(section_data)
        existing = gen_states.get(chapter_index, [])
        if not isinstance(existing, list):
            existing = []
        remaining = slide_plans[len(existing):]

        if not remaining:
            await websocket.send_json({"type": "complete", "total_slides": len(existing)})
            return

        chapter_context = {
            "title": chapter.title,
            "summary": chapter.summary,
            "chapter_index": chapter_index,
            "planning_prompt": project.planning_prompt,
        }

        # Build previous chapters context
        prev_chapters = []
        for i in range(chapter_index):
            prev_slides = gen_states.get(i, [])
            if prev_slides:
                prev_chapters.append({
                    "title": chapters[i].title,
                    "slides": prev_slides,
                })

        def _on_progress(done, total):
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "progress", "done": done, "total": total}),
                loop,
            )

        def _on_batch_done(batch_start, slides):
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "batch_done", "batch_start": batch_start, "slides": slides}),
                loop,
            )

        def _run_batch():
            try:
                prefs = load_preferences()
                batch_size = prefs.get("batch_size", 4)
                results = generate_slides_batch(
                    project_id=project_id,
                    slide_plans=remaining,
                    chapter_context=chapter_context,
                    language=project.language,
                    text_length=text_length,
                    project_override=project.parsed_override,
                    batch_size=batch_size,
                    on_progress=_on_progress,
                    previous_chapters=prev_chapters,
                    on_batch_done=_on_batch_done,
                )

                # Save to DB
                from slidebuddy.config.defaults import DB_PATH
                from slidebuddy.db.migrations import get_connection
                conn = get_connection(DB_PATH)
                try:
                    all_slides = existing + results
                    save_versioned_state(
                        conn, project_id,
                        f"gen_slides_{chapter_index}",
                        chapter_index,
                        all_slides,
                    )
                finally:
                    conn.close()

                asyncio.run_coroutine_threadsafe(
                    queue.put({"type": "complete", "total_slides": len(all_slides)}),
                    loop,
                )
            except Exception as e:
                logger.error("Batch generation failed: %s", e)
                asyncio.run_coroutine_threadsafe(
                    queue.put({"type": "error", "message": str(e)}),
                    loop,
                )

        # Start batch in thread
        loop.run_in_executor(None, _run_batch)

        # Send updates to client
        while True:
            msg = await queue.get()
            await websocket.send_json(msg)
            if msg["type"] in ("complete", "error"):
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for project %s", project_id)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
