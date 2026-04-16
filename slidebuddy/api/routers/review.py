"""Review and export endpoints."""

import json
import logging
import sqlite3
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from slidebuddy.db.helpers import load_versioned_states
from slidebuddy.db.queries import (
    get_chapters_for_project,
    get_project,
    get_slides_for_project,
    update_slide,
)
from slidebuddy.export.pptx_exporter import export_pptx
from slidebuddy.export.txt_exporter import export_gen_slides_txt

from ..dependencies import get_db
from ..schemas import SlideOut, SlideUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{project_id}/slides", response_model=list[SlideOut])
def list_slides(project_id: str, conn=Depends(get_db)):
    slides = get_slides_for_project(conn, project_id)
    return [_slide_to_out(s) for s in slides]


@router.get("/{project_id}/slides/drafts")
def list_draft_slides(project_id: str, conn=Depends(get_db)):
    """Get draft slides from versioned state (gen_slides_*)."""
    states = load_versioned_states(conn, project_id, "gen_slides_")
    return {str(k): v for k, v in sorted(states.items())}


@router.put("/{project_id}/slides/{slide_id}", response_model=SlideOut)
def edit_slide(project_id: str, slide_id: str, body: SlideUpdate, conn=Depends(get_db)):
    """Update a slide's content."""
    from slidebuddy.db.queries import get_slides_for_project
    slides = get_slides_for_project(conn, project_id)
    slide = next((s for s in slides if s.id == slide_id), None)
    if not slide:
        raise HTTPException(404, "Slide not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(slide, field, value)

    return _slide_to_out(update_slide(conn, slide))


@router.get("/{project_id}/export/txt")
def export_txt(project_id: str, conn=Depends(get_db)):
    """Export slides as formatted TXT."""
    project = get_project(conn, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    chapters = get_chapters_for_project(conn, project_id)
    gen_states = load_versioned_states(conn, project_id, "gen_slides_")

    if not gen_states:
        raise HTTPException(400, "No slides generated yet")

    text = export_gen_slides_txt(project.name, gen_states, chapters)
    return Response(
        content=text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{project.name}.txt"'},
    )


@router.get("/{project_id}/export/pptx")
def export_pptx_file(project_id: str, conn=Depends(get_db)):
    """Export slides as PPTX."""
    project = get_project(conn, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    chapters = get_chapters_for_project(conn, project_id)
    gen_states = load_versioned_states(conn, project_id, "gen_slides_")

    if not gen_states:
        raise HTTPException(400, "No slides generated yet")

    pptx_bytes = export_pptx(project.name, gen_states, chapters)
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{project.name}.pptx"'},
    )


def _slide_to_out(s) -> SlideOut:
    return SlideOut(
        id=s.id, chapter_id=s.chapter_id, project_id=s.project_id,
        slide_index=s.slide_index, slide_index_in_chapter=s.slide_index_in_chapter,
        template_type=s.template_type or "unknown",
        title=s.title or "", subtitle=s.subtitle,
        content_json=s.content_json, speaker_notes=s.speaker_notes,
        chain_of_thought=s.chain_of_thought, is_reused=s.is_reused,
        created_at=s.created_at, updated_at=s.updated_at,
    )
