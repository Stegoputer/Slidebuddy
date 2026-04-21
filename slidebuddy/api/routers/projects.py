"""Project CRUD endpoints."""

import shutil
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from slidebuddy.config.defaults import UPLOADS_DIR
from slidebuddy.core.progress import detect_project_step, get_step_index
from slidebuddy.db.models import Project
from slidebuddy.db.queries import (
    create_project,
    delete_project,
    get_all_projects,
    get_project,
    update_project,
)
from slidebuddy.rag.chroma_manager import delete_project_sources_collection

from ..dependencies import get_db
from ..schemas import ProgressOut, ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter()


def _project_to_out(p: Project) -> ProjectOut:
    return ProjectOut(
        id=p.id, name=p.name, topic=p.topic, language=p.language,
        global_text_length=p.global_text_length,
        prompt_override=p.prompt_override, llm_config=p.llm_config,
        planning_prompt=p.planning_prompt,
        created_at=p.created_at, updated_at=p.updated_at,
    )


def _get_or_404(conn: sqlite3.Connection, project_id: str) -> Project:
    project = get_project(conn, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(conn=Depends(get_db)):
    return [_project_to_out(p) for p in get_all_projects(conn)]


@router.post("", response_model=ProjectOut, status_code=201)
def create(body: ProjectCreate, conn=Depends(get_db)):
    project = Project(
        name=body.name,
        topic=body.topic,
        language=body.language,
        global_text_length=body.global_text_length,
    )
    return _project_to_out(create_project(conn, project))


@router.get("/{project_id}", response_model=ProjectOut)
def get(project_id: str, conn=Depends(get_db)):
    return _project_to_out(_get_or_404(conn, project_id))


@router.put("/{project_id}", response_model=ProjectOut)
def update(project_id: str, body: ProjectUpdate, conn=Depends(get_db)):
    project = _get_or_404(conn, project_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    return _project_to_out(update_project(conn, project))


@router.delete("/{project_id}", status_code=204)
def delete(project_id: str, conn=Depends(get_db)):
    _get_or_404(conn, project_id)
    # Clean up files and ChromaDB collection
    upload_dir = UPLOADS_DIR / project_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    try:
        delete_project_sources_collection(project_id)
    except Exception:
        pass
    delete_project(conn, project_id)


@router.get("/{project_id}/progress", response_model=ProgressOut)
def progress(project_id: str, conn=Depends(get_db)):
    _get_or_404(conn, project_id)
    step = detect_project_step(conn, project_id)
    return ProgressOut(
        current_step=step,
        step_index=get_step_index(step),
    )
