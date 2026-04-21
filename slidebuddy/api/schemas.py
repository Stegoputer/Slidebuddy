"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str
    topic: str = ""
    language: str = "de"
    global_text_length: str = "medium"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    topic: Optional[str] = None
    language: Optional[str] = None
    global_text_length: Optional[str] = None
    prompt_override: Optional[str] = None
    llm_config: Optional[str] = None
    planning_prompt: Optional[str] = None


class ProjectOut(BaseModel):
    id: str
    name: str
    topic: str
    language: str
    global_text_length: str
    prompt_override: Optional[str] = None
    llm_config: Optional[str] = None
    planning_prompt: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------

class SourceOut(BaseModel):
    id: str
    project_id: str
    source_type: str
    filename: str
    chunk_count: int
    processing_status: str
    error_message: Optional[str] = None
    created_at: datetime


class YouTubeRequest(BaseModel):
    url: str


# ---------------------------------------------------------------------------
# Chapter
# ---------------------------------------------------------------------------

class ChapterOut(BaseModel):
    id: str
    project_id: str
    chapter_index: int = 0
    title: str = ""
    summary: str = ""
    estimated_slide_count: int = 0
    status: str = "planned"
    source_ids: list[str] = []


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    estimated_slide_count: Optional[int] = None


class ChapterPlanRequest(BaseModel):
    feedback: Optional[str] = None
    strategy: Optional[str] = None  # "auto" (LLM) | "one_per_source" | "full_source_split"


class ChapterBulkUpdate(BaseModel):
    chapters: list[ChapterOut]


class SourceGapOut(BaseModel):
    id: str
    project_id: str
    chapter_id: Optional[str] = None
    description: str
    severity: str = "medium"  # low, medium, high


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------

class SectionPlanOut(BaseModel):
    chapter_index: int = 0
    slides: list[dict] = []


class SlidePlanItem(BaseModel):
    template_type: str = ""
    brief: str = ""
    prompt: Optional[str] = None
    reused_slide_id: Optional[str] = None
    chunks: list[dict] = []


class SectionPlanUpdate(BaseModel):
    slides: list[SlidePlanItem]


# ---------------------------------------------------------------------------
# Slide
# ---------------------------------------------------------------------------

class SlideOut(BaseModel):
    id: str
    chapter_id: str
    project_id: str
    slide_index: int
    slide_index_in_chapter: int
    template_type: str
    title: str = ""
    subtitle: Optional[str] = None
    content_json: Optional[str] = None
    speaker_notes: Optional[str] = None
    chain_of_thought: Optional[str] = None
    is_reused: bool = False
    created_at: datetime
    updated_at: datetime


class SlideUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    content_json: Optional[str] = None
    speaker_notes: Optional[str] = None
    template_type: Optional[str] = None


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class BatchStartRequest(BaseModel):
    chapter_index: int = 0
    slide_index_in_chapter: Optional[int] = None  # None = nächste in Sequenz
    text_length: Optional[str] = None


class GenerateChapterRequest(BaseModel):
    chapter_index: int = 0
    text_length: Optional[str] = None
    batch_size: Optional[int] = None  # None = aus preferences (default: 4)


class BatchStatusOut(BaseModel):
    running: bool
    done: int = 0
    total: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingsOut(BaseModel):
    preferences: dict
    api_keys_configured: dict[str, bool]


class SettingsUpdate(BaseModel):
    preferences: dict


class ApiKeyUpdate(BaseModel):
    key: str


# ---------------------------------------------------------------------------
# Slide Master
# ---------------------------------------------------------------------------

class SlideMasterOut(BaseModel):
    id: str
    name: str
    filename: str
    is_active: bool
    created_at: datetime


class MasterTemplateOut(BaseModel):
    id: str
    master_id: str
    layout_index: int
    layout_name: str
    template_key: str
    display_name: str
    description: str
    placeholder_schema: Optional[str] = None
    content_schema: Optional[str] = None
    generation_prompt: Optional[str] = None
    is_active: bool


class MasterTemplateUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    template_key: Optional[str] = None
    content_schema: Optional[str] = None
    generation_prompt: Optional[str] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

class ProgressOut(BaseModel):
    current_step: str
    step_index: int
    total_steps: int = 4
