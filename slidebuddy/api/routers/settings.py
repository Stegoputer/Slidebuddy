"""Settings and API key management endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from slidebuddy.config.defaults import (
    _API_KEY_PROVIDERS,
    _DEFAULT_TEMPLATE_LABELS,
    get_all_api_keys,
    get_api_key,
    load_preferences,
    save_preferences,
    set_api_key,
    LANGUAGES,
    TEMPLATE_TYPES,
    TEXT_LENGTHS,
)
from slidebuddy.db.queries import get_available_template_types, get_template_labels
from ..dependencies import get_db

from ..schemas import ApiKeyUpdate, SettingsOut, SettingsUpdate

router = APIRouter()


# ---------------------------------------------------------------------------
# Core settings
# ---------------------------------------------------------------------------

@router.get("", response_model=SettingsOut)
def get_settings():
    prefs = load_preferences()
    keys = get_all_api_keys()
    return SettingsOut(
        preferences=prefs,
        api_keys_configured={p: bool(k) for p, k in keys.items()},
    )


@router.put("")
def update_settings(body: SettingsUpdate):
    save_preferences(body.preferences)
    # Clear cached LLM instances so model changes take effect immediately
    from slidebuddy.llm.router import clear_llm_cache
    clear_llm_cache()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

@router.get("/api-keys")
def list_api_keys():
    """Return which providers have keys configured (never exposes actual keys)."""
    keys = get_all_api_keys()
    return {p: bool(k) for p, k in keys.items()}


@router.put("/api-keys/{provider}")
def set_key(provider: str, body: ApiKeyUpdate):
    if provider not in _API_KEY_PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {provider}")
    set_api_key(provider, body.key)
    return {"status": "ok"}


@router.delete("/api-keys/{provider}")
def delete_key(provider: str):
    if provider not in _API_KEY_PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {provider}")
    set_api_key(provider, "")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@router.get("/models")
def list_models():
    """List available models per provider."""
    from slidebuddy.llm.router import get_provider_models
    return get_provider_models()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

class PromptUpdate(BaseModel):
    name: str
    phase: str
    text: str


@router.get("/prompts/phases")
def get_prompt_phases():
    """Return all editable prompt phases with labels and groups."""
    from slidebuddy.llm.prompt_assembler import PROMPT_PHASES, get_default_prompt_text

    phases = {
        "Basis": ["role", "quality_criteria"],
        "Planung": ["chapter_planning", "section_planning"],
        "Generierung": ["slide_generation"],
    }
    labels = {
        "role": "Rolle",
        "quality_criteria": "Qualitätskriterien",
        "chapter_planning": "Kapitelplanung",
        "section_planning": "Sektionsplanung",
        "slide_generation": "Slide-Generierung",
    }
    defaults = {key: get_default_prompt_text(key) for key in PROMPT_PHASES}

    prefs = load_preferences()
    return {
        "groups": phases,
        "labels": labels,
        "defaults": defaults,
        "custom_prompts": prefs.get("custom_prompts", {}),
        "active_prompts": prefs.get("active_prompts", {}),
    }


@router.put("/prompts/active/{phase}")
def set_active_prompt(phase: str, body: dict):
    """Set the active prompt source for a phase ('default' or custom name)."""
    prefs = load_preferences()
    active = prefs.get("active_prompts", {})
    source = body.get("source", "default")
    if source == "default":
        active.pop(phase, None)
    else:
        active[phase] = source
    prefs["active_prompts"] = active
    save_preferences(prefs)
    return {"status": "ok"}


@router.post("/prompts/custom")
def save_custom_prompt(body: PromptUpdate):
    """Create or update a custom prompt."""
    prefs = load_preferences()
    custom = prefs.get("custom_prompts", {})
    custom[body.name] = {"phase": body.phase, "text": body.text}
    prefs["custom_prompts"] = custom
    # Auto-activate
    active = prefs.get("active_prompts", {})
    active[body.phase] = body.name
    prefs["active_prompts"] = active
    save_preferences(prefs)
    return {"status": "ok"}


@router.delete("/prompts/custom/{name}")
def delete_custom_prompt(name: str):
    """Delete a custom prompt."""
    prefs = load_preferences()
    custom = prefs.get("custom_prompts", {})
    prompt = custom.pop(name, None)
    if prompt:
        active = prefs.get("active_prompts", {})
        # Revert to default if this was the active one
        for phase, active_name in list(active.items()):
            if active_name == name:
                active.pop(phase)
        prefs["active_prompts"] = active
    prefs["custom_prompts"] = custom
    save_preferences(prefs)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Debug Log
# ---------------------------------------------------------------------------

@router.get("/debug/summary")
def get_debug_summary():
    """Get prompt debug log statistics."""
    from slidebuddy.llm.prompt_logger import get_log_summary
    return get_log_summary()


@router.delete("/debug/log")
def clear_debug_log():
    """Clear the prompt debug log."""
    from slidebuddy.llm.prompt_logger import clear_log
    clear_log()
    return {"status": "ok"}


@router.get("/debug/download")
def download_debug_log():
    """Download the debug log as JSONL."""
    from slidebuddy.llm.prompt_logger import LOG_PATH
    if not LOG_PATH.exists():
        raise HTTPException(404, "No debug log found")
    return FileResponse(LOG_PATH, filename="prompt_debug.jsonl", media_type="application/jsonl")


# ---------------------------------------------------------------------------
# Templates & Constants
# ---------------------------------------------------------------------------

@router.get("/templates")
def get_templates(conn: sqlite3.Connection = Depends(get_db)):
    """Return available template types with labels."""
    types = get_available_template_types(conn) or TEMPLATE_TYPES
    labels = get_template_labels(conn) or _DEFAULT_TEMPLATE_LABELS
    return {"types": types, "labels": labels}


@router.get("/constants")
def get_constants():
    """Return constant values needed by the frontend."""
    return {
        "languages": LANGUAGES,
        "text_lengths": TEXT_LENGTHS,
        "language_labels": {"de": "Deutsch", "en": "English"},
        "text_length_labels": {"short": "Kurz", "medium": "Mittel", "long": "Ausführlich"},
    }


# ---------------------------------------------------------------------------
# RAG Migration
# ---------------------------------------------------------------------------

@router.post("/rag/migrate-cosine")
def migrate_cosine():
    """Migrate ChromaDB collections from L2 to Cosine distance."""
    from slidebuddy.rag.chroma_manager import migrate_to_cosine
    count = migrate_to_cosine()
    return {"migrated": count}
