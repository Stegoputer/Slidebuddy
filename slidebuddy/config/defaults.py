import json
import logging
from pathlib import Path

import keyring

_logger = logging.getLogger(__name__)

PREFERENCES_PATH = Path.home() / ".slidebuddy" / "preferences.json"

_KEYRING_SERVICE = "slidebuddy"
_API_KEY_PROVIDERS = ("anthropic", "openai", "google")

DEFAULT_PREFERENCES = {
    "default_language": "de",
    "default_text_length": "medium",
    "tonality": "professionell, sachlich",
    "custom_rules": [],
    "preferred_templates": ["numbered", "two_column", "quote"],
    "default_models": {
        "planning": "claude-sonnet-4-20250514",
        "generation": "claude-sonnet-4-20250514",
        "embedding": "text-embedding-3-small",
    },
    "batch_size": 4,
    "custom_prompts": {},
    "active_prompts": {},
    "rag": {
        "n_sources_planning": 5,
        "n_global_planning": 3,
        "n_sources_generation": 3,
        "n_global_generation": 2,
        "n_chunks_per_slide": 3,
        "max_context_chars": 6000,
        "chunk_size": 500,
        "chunk_overlap": 50,
    },
}

TEMPLATE_TYPES = [
    "title",
    "two_column",
    "numbered",
    "three_horizontal",
    "grid",
    "detail",
    "quote",
]

def get_available_template_types() -> list[str]:
    """Return template types from active master or defaults."""
    try:
        from slidebuddy.db.migrations import get_connection
        from slidebuddy.db.queries import get_active_master_templates
        conn = get_connection(DB_PATH)
        master_tpls = get_active_master_templates(conn)
        conn.close()
        if master_tpls:
            return [t.template_key for t in master_tpls if t.is_active]
    except Exception:
        pass
    return TEMPLATE_TYPES


# Display names for default templates (master templates provide their own)
_DEFAULT_TEMPLATE_LABELS = {
    "title": "Startfolie / Kapitelteiler",
    "two_column": "Zwei-Spalten-Vergleich",
    "numbered": "Nummerierte Punkte",
    "three_horizontal": "Drei Spalten",
    "grid": "2x2 Raster",
    "detail": "Detailfolie",
    "quote": "Zitat / These",
}


def get_template_labels() -> dict[str, str]:
    """Return {template_key: display_name} for all available templates."""
    try:
        from slidebuddy.db.migrations import get_connection
        from slidebuddy.db.queries import get_active_master_templates
        conn = get_connection(DB_PATH)
        master_tpls = get_active_master_templates(conn)
        conn.close()
        if master_tpls:
            return {t.template_key: t.display_name for t in master_tpls if t.is_active}
    except Exception:
        pass
    return _DEFAULT_TEMPLATE_LABELS


TEXT_LENGTHS = ["short", "medium", "long"]
LANGUAGES = ["de", "en"]

CONTEXT_WARNING_THRESHOLD = 0.7

# ---------------------------------------------------------------------------
# Generation settings
# ---------------------------------------------------------------------------
DEFAULT_BATCH_SIZE = 4

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "slidebuddy.db"
CHROMA_DIR = DATA_DIR / "chroma"
UPLOADS_DIR = DATA_DIR / "uploads"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Secure API key storage via OS keyring
# ---------------------------------------------------------------------------

def get_api_key(provider: str) -> str:
    """Retrieve an API key from the OS keyring (Windows Credential Manager)."""
    try:
        key = keyring.get_password(_KEYRING_SERVICE, provider)
        return key or ""
    except Exception as e:
        _logger.warning(f"Keyring read failed for {provider}: {e}")
        return ""


def set_api_key(provider: str, key: str) -> None:
    """Store an API key in the OS keyring."""
    try:
        if key:
            keyring.set_password(_KEYRING_SERVICE, provider, key)
        else:
            # Delete key if empty
            try:
                keyring.delete_password(_KEYRING_SERVICE, provider)
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception as e:
        _logger.warning(f"Keyring write failed for {provider}: {e}")


def get_all_api_keys() -> dict[str, str]:
    """Get all API keys from keyring as a dict."""
    return {p: get_api_key(p) for p in _API_KEY_PROVIDERS}


def _migrate_keys_from_preferences() -> None:
    """One-time migration: move API keys from preferences.json to keyring."""
    if not PREFERENCES_PATH.exists():
        return
    try:
        with open(PREFERENCES_PATH, "r", encoding="utf-8") as f:
            stored = json.load(f)
        old_keys = stored.get("api_keys", {})
        if not old_keys:
            return
        migrated = False
        for provider, key in old_keys.items():
            if key:
                set_api_key(provider, key)
                migrated = True
        if migrated:
            # Remove api_keys from preferences file
            stored.pop("api_keys", None)
            with open(PREFERENCES_PATH, "w", encoding="utf-8") as f:
                json.dump(stored, f, indent=2, ensure_ascii=False)
            _logger.info("API keys migrated from preferences.json to OS keyring.")
    except Exception as e:
        _logger.warning(f"API key migration failed: {e}")


# Run migration once on module load
_migrate_keys_from_preferences()


# In-memory cache — avoids re-reading the JSON file on every call.
# Invalidated explicitly when save_preferences() writes new values.
_preferences_cache: dict | None = None


def load_preferences() -> dict:
    """Load preferences with in-memory caching.

    The cache avoids repeated disk reads (previously 3+ per slide generation).
    It's invalidated on save_preferences() so changes take effect immediately.
    """
    global _preferences_cache
    if _preferences_cache is not None:
        return _preferences_cache

    if PREFERENCES_PATH.exists():
        with open(PREFERENCES_PATH, "r", encoding="utf-8") as f:
            stored = json.load(f)
        merged = {**DEFAULT_PREFERENCES, **stored}
        _preferences_cache = merged
        return merged

    _preferences_cache = DEFAULT_PREFERENCES.copy()
    return _preferences_cache


def save_preferences(prefs: dict) -> None:
    global _preferences_cache
    PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PREFERENCES_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2, ensure_ascii=False)
    # Invalidate cache so next load_preferences() picks up new values
    _preferences_cache = None
