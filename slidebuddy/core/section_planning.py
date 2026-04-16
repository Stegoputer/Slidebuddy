"""Section planning node — detailed slide plans with template assignment per chapter."""

import logging

from slidebuddy.config.defaults import load_preferences

logger = logging.getLogger(__name__)


def plan_sections(
    project_id: str,
    chapter: dict,
    language: str,
    project_override: dict | None = None,
    user_feedback: str | None = None,
    extra_chunks: list[dict] | None = None,
    source_ids: list[str] | None = None,
    chunk_mode: str = "chunk",
    source_texts: dict[str, str] | None = None,
) -> dict:
    """Plan detailed slide structure for a single chapter.

    Args:
        project_id: Project ID for RAG queries.
        chapter: Dict with 'title', 'summary', 'estimated_slide_count', 'key_topics'.
        language: Target language.
        project_override: Optional project-level prompt overrides.
        user_feedback: Optional user feedback for iteration.
        extra_chunks: Optional pre-fetched chunks to use.
        source_ids: Source IDs linked to this chapter (for hybrid/full_source modes).
        chunk_mode: "chunk" | "hybrid" | "full_source" — controls chunk assignment.
        source_texts: Mapping of source_id → original_text (for full_source mode).

    Returns:
        Dict with 'slides' (list of slide plans) and 'reasoning'.
    """
    # Route full_source mode to its own content-driven planner. The generic
    # path below is blind to the actual text — it only sees chapter metadata,
    # which in full_source mode causes hallucinated briefs that don't match
    # the segment the slide will actually show.
    if chunk_mode == "full_source" and source_ids and source_texts:
        combined = "\n\n".join(
            source_texts[sid] for sid in source_ids if source_texts.get(sid)
        )
        if combined.strip():
            return _plan_sections_full_source(
                chapter=chapter,
                source_text=combined,
                language=language,
                project_override=project_override,
                user_feedback=user_feedback,
            )
        logger.warning(
            "full_source mode requested but no source text available — falling back to generic planning",
        )

    from langchain_core.messages import HumanMessage, SystemMessage
    from slidebuddy.llm.invoke_helpers import invoke_with_retry
    from slidebuddy.llm.prompt_assembler import assemble_prompt
    from slidebuddy.llm.response_parser import parse_llm_json
    from slidebuddy.llm.router import get_llm

    system_prompt = assemble_prompt(
        phase="section_planning",
        project_override=project_override,
    )

    rag = load_preferences().get("rag", {})

    user_parts = [
        f"KAPITEL: {chapter['title']}",
        f"ZUSAMMENFASSUNG: {chapter.get('summary', '')}",
        f"GESCHÄTZTE FOLIENANZAHL: {chapter.get('estimated_slide_count', 5)}",
        f"KERNTHEMEN: {', '.join(chapter.get('key_topics', []))}",
    ]

    if user_feedback:
        user_parts.append(f"\nUSER-FEEDBACK ZUR ÜBERARBEITUNG:\n{user_feedback}")

    user_prompt = "\n".join(user_parts)

    llm = get_llm("planning")

    import time as _t
    from slidebuddy.llm.prompt_logger import log_llm_call

    # Parse-Retry: Wenn der LLM kaputtes JSON liefert (z.B. halluziniertes Token
    # mitten im Response), bekommt er einen gezielten Korrektur-Hinweis und darf
    # es noch einmal versuchen. invoke_with_retry deckt nur Netzwerkfehler ab.
    result = None
    last_parse_error: str | None = None
    for attempt in range(2):
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        if attempt > 0 and last_parse_error:
            messages.append(HumanMessage(
                content=(
                    f"Deine letzte Antwort war kein gültiges JSON ({last_parse_error}). "
                    "Antworte NUR mit einem JSON-Objekt nach Schema {\"slides\": [...]}. "
                    "Kein Text davor oder danach, keine Erklärungen, keine Code-Fences."
                )
            ))

        _start = _t.perf_counter()
        response = invoke_with_retry(llm, messages, label="section_planning")
        _dur = _t.perf_counter() - _start
        log_llm_call(
            "section_planning", system_prompt, user_prompt, response.content, _dur,
        )

        try:
            result = parse_llm_json(response.content, required_fields=["slides"])
            break
        except ValueError as e:
            last_parse_error = str(e)
            logger.warning(
                "Section planning JSON parse failed (attempt %d/2): %s",
                attempt + 1, e,
            )
            if attempt == 1:
                raise

    # Per-slide chunk assignment using the configured mode.
    # Uses generation settings (n_chunks_per_slide) since chunks feed into generation.
    from slidebuddy.rag.retrieval import assign_chunks_for_slide

    n_per_slide = rag.get("n_chunks_per_slide", 3)
    slides = result.get("slides", [])
    total_slides = len(slides)

    for slide_index, slide in enumerate(slides):
        if slide.get("chunks"):
            continue  # LLM already assigned chunks — respect it

        brief = slide.get("brief", "").strip()
        slide_query = brief if brief else chapter["title"]

        if n_per_slide > 0:
            slide_chunks = assign_chunks_for_slide(
                project_id=project_id,
                query=slide_query,
                source_ids=source_ids or [],
                mode=chunk_mode,
                n_results=n_per_slide,
                source_texts=source_texts,
                slide_index=slide_index,
                total_slides=total_slides,
            )
        else:
            slide_chunks = []

        slide["chunks"] = [
            {
                "text": c["text"],
                "distance": c.get("distance"),
                "selected": True,
                "metadata": c.get("metadata", {}),
            }
            for c in slide_chunks
        ]

    return result


# ---------------------------------------------------------------------------
# Full-source mode — content-driven planning
# ---------------------------------------------------------------------------


def _split_into_segments(text: str, n: int) -> list[str]:
    """Split text into N roughly equal, sequential segments.

    Delegates to the shared utility in text_utils — kept as a private alias
    so existing callers in this module don't break.
    """
    from slidebuddy.core.text_utils import split_into_segments
    return split_into_segments(text, n)


def _plan_sections_full_source(
    chapter: dict,
    source_text: str,
    language: str,
    project_override: dict | None = None,
    user_feedback: str | None = None,
) -> dict:
    """Content-driven section planning with full source text context.

    The LLM sees the complete chapter source text and freely plans
    slide structure based on content — no mechanical pre-splitting.
    Text segments are assigned to slides afterwards for generation.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from slidebuddy.llm.invoke_helpers import invoke_with_retry
    from slidebuddy.llm.prompt_assembler import assemble_prompt
    from slidebuddy.llm.prompt_logger import log_llm_call
    from slidebuddy.llm.response_parser import parse_llm_json
    from slidebuddy.llm.router import get_llm

    planning = load_preferences().get("planning", {})
    min_chars = planning.get("min_chars_per_slide", 1500)
    estimated = max(1, int(chapter.get("estimated_slide_count") or 5))
    # Cap: each slide needs at least min_chars of source text
    max_from_text = max(1, len(source_text.strip()) // min_chars) if source_text.strip() else estimated
    n_slides = min(estimated, max_from_text)

    if not source_text.strip():
        return {"slides": [], "reasoning": "Kein Quelltext vorhanden."}

    lang_label = "Deutsch" if language == "de" else "English"

    system_prompt = assemble_prompt(
        phase="section_planning",
        project_override=project_override,
    )

    user_parts = [
        f"KAPITEL: {chapter['title']}",
        f"ZUSAMMENFASSUNG: {chapter.get('summary', '')}",
        f"SPRACHE: {lang_label}",
        "",
        f"Erstelle exakt {n_slides} Folien basierend auf dem folgenden Quelltext.",
        "Jede Folie muss inhaltlich aus dem Text stammen — nichts erfinden.",
        "Halte einen roten Faden: jede Folie baut logisch auf der vorherigen auf.",
        "Keine inhaltlichen Wiederholungen zwischen Folien.",
        "",
        "Pro Folie lieferst du:",
        '  - "title": praegnanter Folientitel',
        '  - "brief": 2-3 Saetze was auf dieser Folie stehen soll (konkret, nicht generisch)',
        '  - "template_type": passendes Template aus der Liste',
        "",
        f"QUELLTEXT ({len(source_text)} Zeichen):",
        "---",
        source_text,
        "---",
    ]
    if user_feedback:
        user_parts.append(f"\nZIEL DES USERS:\n{user_feedback}")

    user_prompt = "\n".join(user_parts)

    llm = get_llm("planning")

    import time as _t
    result: dict | None = None
    last_parse_error: str | None = None
    for attempt in range(2):
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        if attempt > 0 and last_parse_error:
            messages.append(HumanMessage(
                content=(
                    f"Deine letzte Antwort war kein gültiges JSON ({last_parse_error}). "
                    f"Antworte NUR mit {{\"slides\": [...]}} — exakt {n_slides} Folien, "
                    "keine Erklärungen, keine Code-Fences."
                )
            ))
        _start = _t.perf_counter()
        response = invoke_with_retry(llm, messages, label="section_planning_full_source")
        _dur = _t.perf_counter() - _start
        log_llm_call(
            "section_planning_full_source", system_prompt, user_prompt, response.content, _dur,
        )
        try:
            result = parse_llm_json(response.content, required_fields=["slides"])
            break
        except ValueError as e:
            last_parse_error = str(e)
            logger.warning(
                "Full-source section planning JSON parse failed (attempt %d/2): %s",
                attempt + 1, e,
            )
            if attempt == 1:
                raise

    slides = result.get("slides", []) if isinstance(result, dict) else []

    # Pad or truncate to match expected count
    if len(slides) < n_slides:
        for i in range(len(slides), n_slides):
            slides.append({
                "title": f"{chapter['title']} — Teil {i + 1}",
                "brief": "",
                "template_type": "detail",
            })
    elif len(slides) > n_slides:
        slides = slides[:n_slides]

    # Attach the full chapter source text as chunk for each slide.
    # The slide brief tells the generator what to focus on — the full text
    # ensures enough context. Splitting into tiny segments (~150 tokens)
    # would starve the generator of usable content.
    for i, slide in enumerate(slides):
        slide["chunks"] = [{
            "text": source_text,
            "distance": 0.0,
            "selected": True,
            "metadata": {
                "mode": "full_source",
                "segment_index": i,
                "segment_count": len(slides),
            },
        }]

    return {
        "slides": slides,
        "reasoning": result.get("reasoning", "") if isinstance(result, dict) else "",
    }
