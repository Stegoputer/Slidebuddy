"""Slide master management endpoints."""

import logging
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from slidebuddy.config.defaults import UPLOADS_DIR
from slidebuddy.db.models import SlideMaster
from slidebuddy.db.queries import (
    create_slide_master,
    delete_slide_master,
    get_all_slide_masters,
    get_slide_master,
    get_templates_for_master,
    set_active_slide_master,
    update_master_template,
)

from ..dependencies import get_db
from ..schemas import MasterTemplateOut, MasterTemplateUpdate, SlideMasterOut

logger = logging.getLogger(__name__)
router = APIRouter()


def _master_to_out(m: SlideMaster) -> SlideMasterOut:
    return SlideMasterOut(
        id=m.id, name=m.name, filename=m.filename,
        is_active=m.is_active, created_at=m.created_at,
    )


@router.get("", response_model=list[SlideMasterOut])
def list_masters(conn=Depends(get_db)):
    return [_master_to_out(m) for m in get_all_slide_masters(conn)]


@router.post("", response_model=SlideMasterOut, status_code=201)
async def upload_master(
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Upload a PPTX master template and analyze its layouts."""
    if not file.filename.endswith(".pptx"):
        raise HTTPException(400, "Only .pptx files are supported")

    masters_dir = UPLOADS_DIR / "masters"
    masters_dir.mkdir(parents=True, exist_ok=True)
    file_path = masters_dir / file.filename

    content = await file.read()
    file_path.write_bytes(content)

    master = SlideMaster(
        name=file.filename.rsplit(".", 1)[0],
        filename=file.filename,
        file_path=str(file_path),
    )
    create_slide_master(conn, master)

    # Analyze layouts and build schemas with word limits
    try:
        from slidebuddy.core.master_analyzer import reanalyze_master_templates
        reanalyze_master_templates(conn, master.id)
    except Exception as e:
        logger.error("Master analysis failed: %s", e)

    return _master_to_out(master)


@router.put("/{master_id}/activate")
def activate(master_id: str, conn=Depends(get_db)):
    if not get_slide_master(conn, master_id):
        raise HTTPException(404, "Master not found")
    set_active_slide_master(conn, master_id)
    return {"status": "ok"}


@router.delete("/{master_id}", status_code=204)
def delete(master_id: str, conn=Depends(get_db)):
    master = get_slide_master(conn, master_id)
    if not master:
        raise HTTPException(404, "Master not found")
    # Delete file
    try:
        Path(master.file_path).unlink(missing_ok=True)
    except Exception:
        pass
    delete_slide_master(conn, master_id)


@router.post("/{master_id}/reanalyze")
def reanalyze(master_id: str, conn=Depends(get_db)):
    """Re-analyze an existing master's PPTX to update schemas with word limits.

    Call this after code changes to text capacity estimation, or when
    templates were imported without size data. Updates content_schema,
    generation_prompt, and placeholder_schema for all templates.
    """
    master = get_slide_master(conn, master_id)
    if not master:
        raise HTTPException(404, "Master not found")
    try:
        from slidebuddy.core.master_analyzer import reanalyze_master_templates
        count = reanalyze_master_templates(conn, master_id)
        return {"status": "ok", "updated": count}
    except Exception as e:
        logger.error("Re-analysis failed: %s", e)
        raise HTTPException(500, f"Re-analysis failed: {e}")


@router.get("/{master_id}/templates", response_model=list[MasterTemplateOut])
def list_templates(master_id: str, conn=Depends(get_db)):
    templates = get_templates_for_master(conn, master_id)
    return [
        MasterTemplateOut(
            id=t.id, master_id=t.master_id, layout_index=t.layout_index,
            layout_name=t.layout_name, template_key=t.template_key,
            display_name=t.display_name, description=t.description,
            placeholder_schema=t.placeholder_schema,
            content_schema=t.content_schema,
            generation_prompt=t.generation_prompt, is_active=t.is_active,
        )
        for t in templates
    ]


@router.put("/{master_id}/templates/{template_id}", response_model=MasterTemplateOut)
def update_template(
    master_id: str,
    template_id: str,
    body: MasterTemplateUpdate,
    conn=Depends(get_db),
):
    templates = get_templates_for_master(conn, master_id)
    tpl = next((t for t in templates if t.id == template_id), None)
    if not tpl:
        raise HTTPException(404, "Template not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tpl, field, value)

    updated = update_master_template(conn, tpl)
    return MasterTemplateOut(
        id=updated.id, master_id=updated.master_id,
        layout_index=updated.layout_index, layout_name=updated.layout_name,
        template_key=updated.template_key, display_name=updated.display_name,
        description=updated.description,
        placeholder_schema=updated.placeholder_schema,
        content_schema=updated.content_schema,
        generation_prompt=updated.generation_prompt, is_active=updated.is_active,
    )
