"""Slide generation node — single-slide and batch generation."""

import logging
import time
from collections.abc import Callable

from slidebuddy.config.defaults import load_preferences

logger = logging.getLogger(__name__)

_LENGTH_LABELS = {"short": "Kurz", "medium": "Mittel", "long": "Ausfuehrlich"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_slide(
    project_id: str,
    slide_plan: dict,
    chapter_context: dict,
    language: str,
    text_length: str = "medium",
    slide_index: int = 1,
    total_slides_in_chapter: int = 1,
    project_override: dict | None = None,
    extra_chunks: list[dict] | None = None,
    available_templates: list[str] | None = None,
) -> dict:
    """Generate content for a single slide."""
    from slidebuddy.config.defaults import TEMPLATE_TYPES
    from slidebuddy.llm.prompt_assembler import assemble_prompt
    from slidebuddy.llm.response_parser import parse_llm_json
    from slidebuddy.llm.router import get_llm

    templates = available_templates or TEMPLATE_TYPES
    template_type = slide_plan.get("template_type", templates[0] if templates else "numbered")

    system_prompt = assemble_prompt(
        phase="slide_generation",
        template_type=template_type,
        project_override=project_override,
    )

    rag = load_preferences().get("rag", {})
    source_chunks = _filter_chunks(extra_chunks)
    global_slides = _fetch_global_slides(
        f"{chapter_context['title']} {slide_plan.get('brief', '')}",
        language,
        rag.get("n_global_generation", 0),
    )
    rag_text = _format_rag_context(source_chunks, global_slides)
    user_prompt = _build_single_user_prompt(
        chapter_context, slide_plan, rag_text, text_length, language, slide_index, total_slides_in_chapter
    )

    llm = get_llm("generation")
    response_content = _invoke_and_log(llm, system_prompt, user_prompt, "slide_generation_single", source_chunks)

    result = parse_llm_json(response_content)
    if "slides" in result and isinstance(result.get("slides"), list) and result["slides"] and "title" not in result:
        result = result["slides"][0]
    for field in ("title", "content", "speaker_notes"):
        if field not in result:
            raise ValueError(f"LLM-Antwort fehlt Feld '{field}'.")
    result["_rag_chunks"] = source_chunks
    return _normalize_slide(result, slide_index)


def generate_slides_batch(
    project_id: str,
    slide_plans: list[dict],
    chapter_context: dict,
    language: str,
    text_length: str = "medium",
    project_override: dict | None = None,
    batch_size: int = 4,
    on_progress: Callable | None = None,
    previous_chapters: list[dict] | None = None,
    on_batch_done: Callable | None = None,
    available_templates: list[str] | None = None,
) -> list[dict]:
    """Generate slides in batches — multiple slides per LLM call."""
    from slidebuddy.llm.prompt_assembler import assemble_prompt
    from slidebuddy.llm.response_parser import parse_llm_json
    from slidebuddy.llm.router import get_llm

    all_results: list[dict] = []
    total = len(slide_plans)
    llm = get_llm("generation")
    rag = load_preferences().get("rag", {})

    logger.info("Batch-Generierung gestartet: %d Folien, Batch-Größe %d → %d Batches",
                total, batch_size, -(-total // batch_size))

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_plans = slide_plans[batch_start:batch_end]
        logger.info("Batch %d/%d — Folien %d-%d ...",
                    batch_start // batch_size + 1, -(-total // batch_size),
                    batch_start + 1, batch_end)

        batch_template_types = [p.get("template_type", "numbered") for p in batch_plans]
        system_prompt = assemble_prompt(
            phase="slide_generation_batch",
            template_types=batch_template_types,
            project_override=project_override,
        )

        source_chunks = _collect_batch_chunks(batch_plans)
        global_slides = _fetch_global_slides(
            f"{chapter_context['title']} {' '.join(p.get('brief', '') for p in batch_plans)}",
            language,
            rag.get("n_global_generation", 0),
        )
        rag_text = _format_rag_context(source_chunks, global_slides)
        user_prompt = _build_batch_user_prompt(
            chapter_context, batch_plans, rag_text, text_length, language,
            batch_start, batch_end, total, all_results, previous_chapters,
        )

        label = f"slide_generation_batch_{batch_start + 1}-{batch_end}"
        try:
            response_content = _invoke_and_log(
                llm, system_prompt, user_prompt, label, source_chunks,
                batch_size=len(batch_plans), batch_start=batch_start + 1, batch_end=batch_end,
            )
            slides = parse_llm_json(response_content, required_fields=["slides"])["slides"]
        except Exception as batch_err:
            logger.warning("Batch %d-%d fehlgeschlagen (%s) — Einzelgenerierung als Fallback.",
                           batch_start + 1, batch_end, batch_err)
            slides = _fallback_single_generation(
                project_id, batch_plans, chapter_context, language, text_length,
                project_override, batch_start, total, available_templates,
            )

        # Sanitize: replace None entries in slides list
        slides = [
            s if s is not None else {
                "title": f"Folie {batch_start + i + 1}",
                "content": {},
                "speaker_notes": "",
                "_generation_error": "LLM returned null for this slide",
            }
            for i, s in enumerate(slides)
        ]

        for i, slide in enumerate(slides):
            all_results.append(_normalize_slide(slide, batch_start + i + 1))

        titles = [(s.get("title") or "?")[:50] for s in slides]
        logger.info("Batch %d-%d fertig: %s", batch_start + 1, batch_end, " | ".join(titles))

        if on_batch_done:
            on_batch_done(batch_start, slides)
        if on_progress:
            on_progress(batch_end, total)

    logger.info("Batch-Generierung abgeschlossen: %d Folien generiert.", len(all_results))
    return all_results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _filter_chunks(extra_chunks: list[dict] | None) -> list[dict]:
    """Filter and sort pinned chunks from a slide plan."""
    chunks = [c for c in (extra_chunks or []) if isinstance(c, dict) and c.get("selected", True)]
    chunks.sort(key=lambda c: c.get("distance") if c.get("distance") is not None else float("inf"))
    return chunks


def _collect_batch_chunks(batch_plans: list[dict]) -> list[dict]:
    """Deduplicate and sort pinned chunks across all plans in a batch."""
    chunks: list[dict] = []
    seen: set[str] = set()
    for plan in batch_plans:
        for chunk in plan.get("chunks", []):
            if not isinstance(chunk, dict) or not chunk.get("text"):
                continue
            if chunk.get("selected", True) and chunk["text"] not in seen:
                chunks.append(chunk)
                seen.add(chunk["text"])
    chunks.sort(key=lambda c: c.get("distance") if c.get("distance") is not None else float("inf"))
    return chunks


def _fetch_global_slides(query: str, language: str, n_global: int) -> list[dict]:
    """Fetch global reference slides; returns [] when n_global == 0."""
    if n_global <= 0:
        return []
    from slidebuddy.rag.retrieval import search_global_slides
    return search_global_slides(query, language=language, n_results=n_global)


def _build_single_user_prompt(
    chapter_context: dict,
    slide_plan: dict,
    rag_text: str,
    text_length: str,
    language: str,
    slide_index: int,
    total: int,
) -> str:
    lang_label = "Deutsch" if language == "de" else "English"
    parts = [
        f"KAPITEL: {chapter_context['title']}",
        f"KAPITEL-ZUSAMMENFASSUNG: {chapter_context.get('summary', '')}",
    ]
    planning_prompt = chapter_context.get("planning_prompt")
    if planning_prompt:
        parts.append(f"\nZIEL DES USERS:\n{planning_prompt}")
    if rag_text:
        parts.append(f"\nRELEVANTER QUELLEN-KONTEXT:\n{rag_text}")
    parts.extend([
        f"\nAUFGABE: Erstelle Folie {slide_index} von {total}",
        f"TEMPLATE: {slide_plan.get('template_type', 'numbered')}",
        f"KURZBESCHREIBUNG: {slide_plan.get('brief', '')}",
        f"TEXTUMFANG: {_LENGTH_LABELS.get(text_length, 'Mittel')}",
        f"SPRACHE: {lang_label}",
    ])
    return "\n".join(parts)


def _build_batch_user_prompt(
    chapter_context: dict,
    batch_plans: list[dict],
    rag_text: str,
    text_length: str,
    language: str,
    batch_start: int,
    batch_end: int,
    total: int,
    all_results: list[dict],
    previous_chapters: list[dict] | None,
) -> str:
    lang_label = "Deutsch" if language == "de" else "English"
    parts = [
        f"KAPITEL: {chapter_context['title']}",
        f"KAPITEL-ZUSAMMENFASSUNG: {chapter_context.get('summary', '')}",
    ]

    planning_prompt = chapter_context.get("planning_prompt")
    if planning_prompt:
        parts.append(f"\nZIEL DES USERS:\n{planning_prompt}")

    if previous_chapters and batch_start == 0:
        prev_lines = [
            f"  - {ch.get('title', '')}: {ch.get('summary', '')}"
            for ch in previous_chapters[-3:]
        ]
        if prev_lines:
            parts.append("\nVORHERIGE KAPITEL (baue darauf auf, wiederhole nichts):\n" + "\n".join(prev_lines))

    if all_results:
        prev_summaries = "\n".join(
            f"Folie {r.get('slide_index', '?')}: {r.get('key_summary', '')}"
            for r in all_results[-3:]
        )
        parts.append(f"\nBISHERIGE FOLIEN IN DIESEM KAPITEL:\n{prev_summaries}")

    if rag_text:
        parts.append(f"\nRELEVANTER QUELLEN-KONTEXT:\n{rag_text}")

    slide_descriptions = [
        f"  Folie {batch_start + i + 1}: TEMPLATE={p.get('template_type', 'numbered')} | BRIEF={p.get('brief', '')}"
        for i, p in enumerate(batch_plans)
    ]
    parts.extend([
        f"\nAUFGABE: Generiere {len(batch_plans)} Folien (Folie {batch_start + 1} bis {batch_end} von {total})",
        "FOLIEN-BESCHREIBUNGEN:\n" + "\n".join(slide_descriptions),
        f"TEXTUMFANG: {_LENGTH_LABELS.get(text_length, 'Mittel')}",
        f"SPRACHE: {lang_label}",
    ])
    return "\n".join(parts)


def _invoke_and_log(
    llm,
    system_prompt: str,
    user_prompt: str,
    label: str,
    chunks: list[dict],
    **metadata,
) -> str:
    """Invoke the LLM with retry, log the call, return response content."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from slidebuddy.llm.invoke_helpers import invoke_with_retry
    from slidebuddy.llm.prompt_logger import log_llm_call

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    start = time.perf_counter()
    response = invoke_with_retry(llm, messages, label=label)
    duration = time.perf_counter() - start
    log_llm_call(label, system_prompt, user_prompt, response.content, duration,
                 chunks=chunks, metadata=metadata or None)
    return response.content


def _normalize_slide(slide: dict, slide_index: int) -> dict:
    """Ensure required defaults on a slide result dict."""
    slide.setdefault("subtitle", None)
    slide.setdefault("chain_of_thought", "")
    slide.setdefault("key_summary", slide.get("title", ""))
    slide["slide_index"] = slide_index

    # Post-processing: enforce word limits from template schema
    template_type = slide.get("template_type")
    content = slide.get("content")
    if template_type and isinstance(content, dict):
        slide["content"] = _enforce_word_limits(template_type, content)

    return slide


def _fallback_single_generation(
    project_id: str,
    batch_plans: list[dict],
    chapter_context: dict,
    language: str,
    text_length: str,
    project_override: dict | None,
    batch_start: int,
    total: int,
    available_templates: list[str] | None,
) -> list[dict]:
    """Fall back to per-slide generation when a batch call fails."""
    slides = []
    for i, plan in enumerate(batch_plans):
        try:
            slide = generate_slide(
                project_id=project_id,
                slide_plan=plan,
                chapter_context=chapter_context,
                language=language,
                text_length=text_length,
                slide_index=batch_start + i + 1,
                total_slides_in_chapter=total,
                project_override=project_override,
                extra_chunks=plan.get("chunks"),
                available_templates=available_templates,
            )
            slides.append(slide)
        except Exception as slide_err:
            logger.error("Einzelgenerierung Folie %d fehlgeschlagen: %s", batch_start + i + 1, slide_err)
            slides.append({
                "title": plan.get("brief", f"Folie {batch_start + i + 1}"),
                "content": {},
                "speaker_notes": "",
                "subtitle": None,
                "chain_of_thought": "",
                "key_summary": "",
                "_generation_error": str(slide_err),
            })
    return slides


# ---------------------------------------------------------------------------
# Post-processing: enforce word limits from template content_schema
# ---------------------------------------------------------------------------

# Cache: template_type → {field_name: max_words}
_word_limit_cache: dict[str, dict[str, int]] = {}


def _get_word_limits(template_type: str) -> dict[str, int]:
    """Load max_words per field from the template's content_schema.

    Parses hints like "str — max 7 Zeilen, 31 Woerter" into {field: 31}.
    Returns empty dict for built-in (non-master) templates that have no
    word limits, or if the schema can't be parsed.
    """
    if template_type in _word_limit_cache:
        return _word_limit_cache[template_type]

    limits: dict[str, int] = {}
    try:
        from slidebuddy.config.defaults import DB_PATH
        from slidebuddy.db.migrations import get_connection
        from slidebuddy.db.queries import get_active_master_templates
        import json
        import re

        conn = get_connection(DB_PATH)
        templates = get_active_master_templates(conn)
        conn.close()

        for tpl in templates:
            if tpl.template_key == template_type and tpl.content_schema:
                schema = json.loads(tpl.content_schema)
                for field_name, hint in schema.items():
                    if not isinstance(hint, str):
                        continue
                    m = re.search(r"(\d+)\s*Woerter", hint)
                    if m:
                        limits[field_name] = int(m.group(1))
                break
    except Exception as e:
        logger.debug("Could not load word limits for %s: %s", template_type, e)

    _word_limit_cache[template_type] = limits
    return limits


def _truncate_to_words(text: str, max_words: int) -> str:
    """Truncate text to max_words, preserving sentence boundaries where possible."""
    words = text.split()
    if len(words) <= max_words:
        return text

    # Try to end at a sentence boundary within the limit
    truncated = " ".join(words[:max_words])
    # Find the last sentence-ending punctuation
    for end_char in (".", "!", "?"):
        last_pos = truncated.rfind(end_char)
        if last_pos > len(truncated) * 0.5:  # at least half the text
            return truncated[: last_pos + 1]

    # No good sentence boundary — hard cut with ellipsis
    return truncated.rstrip(",.;:!? ") + " …"


def _enforce_word_limits(template_type: str, content: dict) -> dict:
    """Enforce per-field word limits on generated content.

    Loads the template's content_schema, extracts max_words per field,
    and truncates any field that exceeds its limit. This is a safety net
    for when the LLM ignores TEXTLAENGEN hints in the prompt.
    """
    limits = _get_word_limits(template_type)
    if not limits:
        return content  # No master template or no limits defined

    trimmed = False
    for field_name, max_words in limits.items():
        if field_name not in content:
            continue
        value = content[field_name]
        if not isinstance(value, str):
            continue
        word_count = len(value.split())
        # Allow 20% tolerance to avoid cutting mid-thought on borderline cases
        if word_count > max_words * 1.2:
            content[field_name] = _truncate_to_words(value, max_words)
            trimmed = True
            logger.info(
                "Trimmed field '%s' from %d to %d words (limit: %d)",
                field_name, word_count, len(content[field_name].split()), max_words,
            )

    if trimmed:
        logger.info("Word limit enforcement applied for template '%s'", template_type)
    return content


def _format_rag_context(source_chunks: list[dict], global_slides: list[dict]) -> str:
    """Format RAG results for the prompt."""
    parts = []
    if source_chunks:
        parts.append("Aus Projekt-Quellen:")
        for chunk in source_chunks:
            text = chunk.get("text", "")
            if text:
                meta = chunk.get("metadata", {})
                parts.append(f"  [{meta.get('filename', '?')}]: {text}")
    if global_slides:
        parts.append("\nAus frueheren Praesentationen:")
        for slide in global_slides:
            text = slide.get("text", "")
            if text:
                parts.append(f"  {text}")
    return "\n".join(parts)
