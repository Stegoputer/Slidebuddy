import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


def new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Project:
    id: str = field(default_factory=new_id)
    name: str = ""
    topic: str = ""
    language: str = "de"
    prompt_override: Optional[str] = None  # JSON string
    global_text_length: str = "medium"
    llm_config: Optional[str] = None  # JSON string
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def parsed_override(self) -> dict | None:
        """Parse prompt_override JSON, returning None on missing/invalid data."""
        if not self.prompt_override:
            return None
        try:
            return json.loads(self.prompt_override)
        except json.JSONDecodeError:
            return None


@dataclass
class Version:
    id: str = field(default_factory=new_id)
    project_id: str = ""
    chapter_index: int = 0
    version_number: int = 1
    state: str = "draft"  # draft, reviewed, final
    state_json: Optional[str] = None  # JSON
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Chapter:
    id: str = field(default_factory=new_id)
    project_id: str = ""
    version_id: Optional[str] = None
    chapter_index: int = 0
    title: str = ""
    summary: str = ""
    estimated_slide_count: int = 0
    status: str = "planned"  # planned, generating, review, approved


@dataclass
class Slide:
    id: str = field(default_factory=new_id)
    chapter_id: str = ""
    project_id: str = ""
    slide_index: int = 0
    slide_index_in_chapter: int = 0
    template_type: str = ""
    title: str = ""
    subtitle: Optional[str] = None
    content_json: Optional[str] = None
    speaker_notes: Optional[str] = None
    chain_of_thought: Optional[str] = None
    is_reused: bool = False
    source_slide_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Source:
    id: str = field(default_factory=new_id)
    project_id: str = ""
    source_type: str = ""  # pdf, pptx, txt, markdown, youtube, excel, transcript
    filename: str = ""
    original_text: Optional[str] = None
    chunk_count: int = 0
    processing_status: str = "pending"  # pending, processing, done, error
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SlideMaster:
    id: str = field(default_factory=new_id)
    name: str = ""
    filename: str = ""
    file_path: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MasterTemplate:
    id: str = field(default_factory=new_id)
    master_id: str = ""
    layout_index: int = 0
    layout_name: str = ""
    template_key: str = ""
    display_name: str = ""
    description: str = ""
    placeholder_schema: Optional[str] = None  # JSON
    content_schema: Optional[str] = None  # JSON
    generation_prompt: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SourceGap:
    id: str = field(default_factory=new_id)
    project_id: str = ""
    chapter_id: Optional[str] = None
    description: str = ""
    status: str = "open"  # open, resolved
    created_at: datetime = field(default_factory=datetime.utcnow)
