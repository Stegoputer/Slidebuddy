from functools import lru_cache
from pathlib import Path

from slidebuddy.config.defaults import PROMPTS_DIR, load_preferences

# Prompt files never change at runtime, so we cache them permanently.
# lru_cache(maxsize=32) keeps the last 32 unique file reads in memory
# and returns cached results for repeated reads — zero disk I/O after
# the first call for each file.


@lru_cache(maxsize=32)
def load_prompt_module(module_path: str) -> str:
    full_path = PROMPTS_DIR / module_path
    if not full_path.exists():
        raise FileNotFoundError(f"Prompt module not found: {full_path}")
    return full_path.read_text(encoding="utf-8").strip()


def load_template_definition(template_type: str) -> str:
    # Check in-memory cache first
    if template_type in _single_template_cache:
        return _single_template_cache[template_type]

    result = _load_template_definition_uncached(template_type)
    _single_template_cache[template_type] = result
    return result


def _load_template_definition_uncached(template_type: str) -> str:
    # Check active master templates first
    master_def = _get_master_template_definition(template_type)
    if master_def:
        return master_def

    # Check custom templates
    custom_path = PROMPTS_DIR / "templates" / "custom"
    if custom_path.exists():
        for f in custom_path.glob("*.txt"):
            content = f.read_text(encoding="utf-8")
            if f"TEMPLATE: {template_type}" in content or f"TEMPLATE-NAME: {template_type}" in content:
                return content.strip()

    # Standard templates
    template_map = {
        "title": "template_01_title.txt",
        "two_column": "template_02_two_column.txt",
        "numbered": "template_03_numbered.txt",
        "three_horizontal": "template_04_three_horizontal.txt",
        "grid": "template_05_grid.txt",
        "detail": "template_06_detail.txt",
        "quote": "template_07_quote.txt",
    }
    filename = template_map.get(template_type)
    if not filename:
        return f"TEMPLATE: {template_type}\n\nGeneriere Inhalte passend zum Template-Typ '{template_type}'."
    return load_prompt_module(f"templates/{filename}")


_template_defs_cache: str | None = None
_template_defs_master_id: str | None = "__unset__"
_single_template_cache: dict[str, str] = {}  # template_key -> formatted definition


def load_all_template_definitions() -> str:
    """Load all template definitions. Cached per active master — auto-invalidates on master switch."""
    global _template_defs_cache, _template_defs_master_id

    current_master_id = _get_active_master_id()
    if _template_defs_cache is not None and _template_defs_master_id == current_master_id:
        return _template_defs_cache

    # Cache miss — rebuild
    master_defs = _get_all_master_template_definitions()
    if master_defs:
        _template_defs_cache = master_defs
    else:
        templates = []
        template_dir = PROMPTS_DIR / "templates"
        for f in sorted(template_dir.glob("template_*.txt")):
            templates.append(f.read_text(encoding="utf-8").strip())
        custom_dir = template_dir / "custom"
        if custom_dir.exists():
            for f in sorted(custom_dir.glob("*.txt")):
                templates.append(f.read_text(encoding="utf-8").strip())
        _template_defs_cache = "\n\n---\n\n".join(templates)

    _template_defs_master_id = current_master_id
    return _template_defs_cache


def clear_template_cache():
    """Force cache invalidation (called on master switch)."""
    global _template_defs_cache, _template_defs_master_id, _single_template_cache, _active_master_id_cache
    _template_defs_cache = None
    _template_defs_master_id = "__unset__"
    _single_template_cache.clear()
    _active_master_id_cache = "__unset__"


# Maps each prompt phase to its default file path under PROMPTS_DIR.
# Users can override any of these by saving a custom prompt with the same phase key.
PROMPT_PHASES = {
    "role": "base/role.txt",
    "quality_criteria": "base/quality_criteria.txt",
    "chapter_planning": "planning/chapter_planning.txt",
    "section_planning": "planning/section_planning.txt",
    "slide_generation": "generation/slide_generation.txt",
}


def get_prompt_text(phase_key: str) -> str:
    """Get prompt text for a phase — custom override or default file.

    Checks preferences['active_prompts'] first. If a custom prompt is active
    for this phase, returns it. Otherwise loads the default from disk.
    """
    prefs = load_preferences()
    active = prefs.get("active_prompts", {})

    # If user has set a custom prompt for this phase, use it
    if phase_key in active:
        prompt_name = active[phase_key]
        custom_prompts = prefs.get("custom_prompts", {})
        if prompt_name in custom_prompts:
            return custom_prompts[prompt_name].get("text", "")

    # Default: load from file
    file_path = PROMPT_PHASES.get(phase_key)
    if not file_path:
        return ""
    return load_prompt_module(file_path)


def get_default_prompt_text(phase_key: str) -> str:
    """Get the default prompt text from file (ignoring custom overrides)."""
    file_path = PROMPT_PHASES.get(phase_key)
    if not file_path:
        return ""
    return load_prompt_module(file_path)


def assemble_prompt(
    phase: str,
    template_type: str | None = None,
    template_types: list[str] | None = None,
    project_override: dict | None = None,
) -> str:
    """Assemble system prompt based on phase.

    Phases and their modules:
    - chapter_planning: role + quality_criteria + chapter_planning
    - section_planning: role + section_planning + compact template list
    - slide_generation: role + quality_criteria + slide_generation + single template
    - slide_generation_batch: role + quality_criteria + slide_generation + batch templates
    """
    parts = []

    if phase == "chapter_planning":
        parts.append(get_prompt_text("role"))
        parts.append(get_prompt_text("quality_criteria"))
        parts.append(get_prompt_text("chapter_planning"))
    elif phase == "section_planning":
        parts.append(get_prompt_text("role"))
        parts.append(get_prompt_text("section_planning"))
        parts.append("VERFUEGBARE TEMPLATES:\n\n" + _load_template_summary())
    elif phase == "slide_generation":
        parts.append(get_prompt_text("role"))
        parts.append(get_prompt_text("quality_criteria"))
        parts.append(get_prompt_text("slide_generation"))
        if template_type:
            parts.append("TEMPLATE FUER DIESE FOLIE:\n\n" + load_template_definition(template_type))
    elif phase == "slide_generation_batch":
        parts.append(get_prompt_text("role"))
        parts.append(get_prompt_text("quality_criteria"))
        parts.append(get_prompt_text("slide_generation"))
        if template_types:
            tpl_defs = _load_template_definitions_for(template_types)
        else:
            tpl_defs = load_all_template_definitions()
        parts.append("TEMPLATE-DEFINITIONEN:\n\n" + tpl_defs)
    else:
        raise ValueError(f"Unknown phase: {phase}")

    # Add user preferences
    prefs = load_preferences()
    pref_lines = []
    if prefs.get("tonality"):
        pref_lines.append(f"Tonalität: {prefs['tonality']}")
    if prefs.get("custom_rules"):
        pref_lines.append("Zusätzliche Regeln:\n" + "\n".join(f"- {r}" for r in prefs["custom_rules"]))
    if pref_lines:
        parts.append("USER-PRÄFERENZEN:\n\n" + "\n".join(pref_lines))

    # Add project override
    if project_override:
        override_lines = []
        if project_override.get("topic_context"):
            override_lines.append(f"Projektkontext: {project_override['topic_context']}")
        if project_override.get("vocabulary"):
            override_lines.append(f"Fachvokabular: {', '.join(project_override['vocabulary'])}")
        if project_override.get("text_length_override"):
            override_lines.append(f"Textumfang: {project_override['text_length_override']}")
        if project_override.get("additional_rules"):
            override_lines.append("Projekt-Regeln:\n" + "\n".join(f"- {r}" for r in project_override["additional_rules"]))
        if override_lines:
            parts.append("PROJEKT-SPEZIFISCH:\n\n" + "\n".join(override_lines))

    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Master template integration
# ---------------------------------------------------------------------------

_active_master_id_cache: str | None = "__unset__"


def _load_template_definitions_for(template_types: list[str]) -> str:
    """Load template definitions for only the specified template types.

    Much more efficient than load_all_template_definitions() when only
    a few templates are needed (e.g. batch with 4 slides using 2-3 types).
    """
    unique_types = list(dict.fromkeys(template_types))  # deduplicate, preserve order
    parts = []
    for tpl_type in unique_types:
        try:
            parts.append(load_template_definition(tpl_type))
        except Exception:
            parts.append(f"TEMPLATE: {tpl_type}\n\nGeneriere Inhalte passend zum Template-Typ '{tpl_type}'.")
    return "\n\n---\n\n".join(parts)


def _get_active_master_id() -> str | None:
    """Get the ID of the currently active master. Cached for the session — cleared by clear_template_cache()."""
    global _active_master_id_cache
    if _active_master_id_cache != "__unset__":
        return _active_master_id_cache
    try:
        from slidebuddy.config.defaults import DB_PATH
        from slidebuddy.db.migrations import get_connection
        from slidebuddy.db.queries import get_active_slide_master

        conn = get_connection(DB_PATH)
        master = get_active_slide_master(conn)
        conn.close()
        _active_master_id_cache = master.id if master else None
    except Exception:
        _active_master_id_cache = None
    return _active_master_id_cache


def _get_master_template_definition(template_key: str) -> str | None:
    """Get a single master template definition formatted like a prompt module."""
    try:
        from slidebuddy.config.defaults import DB_PATH
        from slidebuddy.db.migrations import get_connection
        from slidebuddy.db.queries import get_active_master_templates

        conn = get_connection(DB_PATH)
        templates = get_active_master_templates(conn)
        conn.close()

        for tpl in templates:
            if tpl.template_key == template_key:
                return _format_master_template(tpl)
    except Exception:
        pass
    return None


def _get_all_master_template_definitions() -> str | None:
    """Get all active master template definitions formatted as prompt text."""
    try:
        from slidebuddy.config.defaults import DB_PATH
        from slidebuddy.db.migrations import get_connection
        from slidebuddy.db.queries import get_active_master_templates
        import json

        conn = get_connection(DB_PATH)
        templates = get_active_master_templates(conn)
        conn.close()

        if not templates:
            return None

        parts = [_format_master_template(tpl) for tpl in templates]
        return "\n\n---\n\n".join(parts)
    except Exception:
        return None


def _load_template_summary() -> str:
    """Load a compact template list for section planning — name + description only.

    Section planning only needs to know WHICH templates exist and WHAT they're for,
    not the full JSON schema or generation hints. This reduces ~27,500 chars to ~2,000.
    """
    # Try master templates first
    summary = _get_master_template_summary()
    if summary:
        return summary

    # Fallback to file-based templates
    from slidebuddy.config.defaults import get_available_template_types, get_template_labels
    labels = get_template_labels()
    lines = []
    for key in get_available_template_types():
        label = labels.get(key, key)
        lines.append(f"- {key}: {label}")
    return "\n".join(lines) if lines else "Keine Templates verfuegbar."


def _get_master_template_summary() -> str | None:
    """Get compact template list from active master: key + display_name + purpose.

    Extracts the ZIEL (purpose) from generation_prompt for a meaningful description,
    instead of using the raw placeholder listing in description.
    """
    try:
        from slidebuddy.config.defaults import DB_PATH
        from slidebuddy.db.migrations import get_connection
        from slidebuddy.db.queries import get_active_master_templates
        import re

        conn = get_connection(DB_PATH)
        templates = get_active_master_templates(conn)
        conn.close()

        if not templates:
            return None

        lines = []
        for tpl in templates:
            # Extract purpose from generation_prompt ZIEL line
            purpose = ""
            if tpl.generation_prompt:
                m = re.search(r'ZIEL[^:]*:\s*(.+?)\.', tpl.generation_prompt)
                if m:
                    purpose = m.group(1).strip()
            if not purpose:
                purpose = tpl.description

            lines.append(f"- {tpl.template_key} ({tpl.display_name}): {purpose}")
        return "\n".join(lines)
    except Exception:
        return None


def _format_master_template(tpl) -> str:
    """Format a MasterTemplate into the same text format as file-based templates."""
    import json

    lines = [f"TEMPLATE: {tpl.template_key} ({tpl.display_name})"]
    lines.append("")
    lines.append(f"BESCHREIBUNG: {tpl.description}")
    lines.append("")

    # Content structure from placeholder schema
    if tpl.placeholder_schema:
        try:
            phs = json.loads(tpl.placeholder_schema)
            lines.append("CONTENT-STRUKTUR:")
            for ph in phs:
                lines.append(f"- {ph['name']} ({ph['type']})")
            lines.append("")
        except json.JSONDecodeError:
            pass

    # JSON schema
    if tpl.content_schema:
        lines.append("JSON-SCHEMA:")
        lines.append(tpl.content_schema)
        lines.append("")

    # Generation hints
    if tpl.generation_prompt:
        lines.append("HINWEISE:")
        lines.append(tpl.generation_prompt)

    return "\n".join(lines)
