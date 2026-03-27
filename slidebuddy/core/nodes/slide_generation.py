"""Slide generation node — single-slide and batch generation."""

import logging
from collections.abc import Callable

from langchain_core.messages import HumanMessage, SystemMessage

from slidebuddy.config.defaults import load_preferences
from slidebuddy.llm.prompt_assembler import assemble_prompt
from slidebuddy.llm.response_parser import parse_llm_json
from slidebuddy.llm.router import get_llm
from slidebuddy.rag.retrieval import search_all

logger = logging.getLogger(__name__)

_LENGTH_LABELS = {"short": "Kurz", "medium": "Mittel", "long": "Ausfuehrlich"}


# ---------------------------------------------------------------------------
# Public API — one function per strategy
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
) -> dict:
    """Generate content for a single slide."""
    from slidebuddy.config.defaults import get_available_template_types
    available = get_available_template_types()
    template_type = slide_plan.get("template_type", available[0] if available else "numbered")

    system_prompt = assemble_prompt(
        phase="slide_generation",
        template_type=template_type,
        project_override=project_override,
    )

    rag = load_preferences().get("rag", {})
    source_chunks, global_slides = search_all(
        project_id,
        f"{chapter_context['title']} {slide_plan.get('brief', '')}",
        language=language,
        n_sources=rag.get("n_sources_generation", 3),
        n_global=rag.get("n_global_generation", 2),
    )

    # Merge pinned chunks (from section planning) with auto-retrieved
    if extra_chunks:
        seen = {c["text"] for c in source_chunks}
        for ec in extra_chunks:
            if ec["text"] not in seen:
                source_chunks.append(ec)
                seen.add(ec["text"])

    # Sort by distance ascending (most relevant first) so context budget is used on best chunks
    source_chunks.sort(key=lambda c: c.get("distance") if c.get("distance") is not None else float("inf"))

    rag_text = _format_rag_context(source_chunks, global_slides, max_total_chars=rag.get("max_context_chars", 6000))

    lang_label = "Deutsch" if language == "de" else "English"

    user_parts = [
        f"KAPITEL: {chapter_context['title']}",
        f"KAPITEL-ZUSAMMENFASSUNG: {chapter_context.get('summary', '')}",
    ]

    if rag_text:
        user_parts.append(f"\nRELEVANTER QUELLEN-KONTEXT:\n{rag_text}")

    user_parts.extend([
        f"\nAUFGABE: Erstelle Folie {slide_index} von {total_slides_in_chapter}",
        f"TEMPLATE: {template_type}",
        f"KURZBESCHREIBUNG: {slide_plan.get('brief', '')}",
        f"TEXTUMFANG: {_LENGTH_LABELS.get(text_length, 'Mittel')}",
        f"SPRACHE: {lang_label}",
    ])

    user_prompt = "\n".join(user_parts)

    llm = get_llm("generation")

    import time as _t
    _start = _t.perf_counter()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    _dur = _t.perf_counter() - _start

    from slidebuddy.llm.prompt_logger import log_llm_call
    log_llm_call(
        "slide_generation_single", system_prompt, user_prompt, response.content, _dur,
        chunks=source_chunks,
    )

    result = parse_llm_json(response.content, required_fields=["title", "content", "speaker_notes"])
    result.setdefault("subtitle", None)
    result.setdefault("chain_of_thought", "")
    result.setdefault("key_summary", result["title"])
    result["_rag_chunks"] = source_chunks
    return result


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
) -> list[dict]:
    """Generate slides in batches — multiple slides per LLM call.

    Good compromise: coherent within each batch, fewer API calls than sequential.
    """
    all_results = []
    total = len(slide_plans)
    llm = get_llm("generation")
    rag = load_preferences().get("rag", {})

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_plans = slide_plans[batch_start:batch_end]

        # Only include templates used in THIS batch — not all 19
        batch_template_types = [p.get("template_type", "numbered") for p in batch_plans]
        system_prompt = assemble_prompt(
            phase="slide_generation_batch",
            template_types=batch_template_types,
            project_override=project_override,
        )

        query = f"{chapter_context['title']} {' '.join(p.get('brief', '') for p in batch_plans)}"
        source_chunks, global_slides = search_all(
            project_id, query, language=language,
            n_sources=rag.get("n_sources_generation", 3),
            n_global=rag.get("n_global_generation", 2),
        )

        # Merge per-slide pinned chunks from section plans
        seen = {c["text"] for c in source_chunks}
        for p in batch_plans:
            for ec in p.get("chunks", []):
                if ec.get("selected", True) and ec["text"] not in seen:
                    source_chunks.append(ec)
                    seen.add(ec["text"])

        # Sort by distance ascending (most relevant first) so context budget is used on best chunks
        source_chunks.sort(key=lambda c: c.get("distance") if c.get("distance") is not None else float("inf"))

        rag_text = _format_rag_context(source_chunks, global_slides, max_total_chars=rag.get("max_context_chars", 6000))

        lang_label = "Deutsch" if language == "de" else "English"

        user_parts = [
            f"KAPITEL: {chapter_context['title']}",
            f"KAPITEL-ZUSAMMENFASSUNG: {chapter_context.get('summary', '')}",
        ]

        # Context from previous chapters — enables cross-chapter coherence
        if previous_chapters and batch_start == 0:
            prev_ch_lines = []
            for ch in previous_chapters[-3:]:  # Last 3 chapters max
                ch_title = ch.get("title", "")
                ch_summary = ch.get("summary", "")
                prev_ch_lines.append(f"  - {ch_title}: {ch_summary}")
            if prev_ch_lines:
                user_parts.append("\nVORHERIGE KAPITEL (baue darauf auf, wiederhole nichts):\n" + "\n".join(prev_ch_lines))

        if all_results:
            prev_summaries = "\n".join(
                f"Folie {r.get('slide_index', '?')}: {r.get('key_summary', '')}"
                for r in all_results[-3:]
            )
            user_parts.append(f"\nBISHERIGE FOLIEN IN DIESEM KAPITEL:\n{prev_summaries}")

        if rag_text:
            user_parts.append(f"\nRELEVANTER QUELLEN-KONTEXT:\n{rag_text}")

        # Describe each slide in the batch
        slide_descriptions = []
        for i, plan in enumerate(batch_plans):
            global_idx = batch_start + i + 1
            slide_descriptions.append(
                f"  Folie {global_idx}: TEMPLATE={plan.get('template_type', 'numbered')} | "
                f"BRIEF={plan.get('brief', '')}"
            )

        user_parts.extend([
            f"\nAUFGABE: Generiere {len(batch_plans)} Folien (Folie {batch_start + 1} bis {batch_end} von {total})",
            "FOLIEN-BESCHREIBUNGEN:\n" + "\n".join(slide_descriptions),
            f"TEXTUMFANG: {_LENGTH_LABELS.get(text_length, 'Mittel')}",
            f"SPRACHE: {lang_label}",
        ])

        user_prompt = "\n".join(user_parts)

        import time as _t
        _start = _t.perf_counter()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        _dur = _t.perf_counter() - _start

        from slidebuddy.llm.prompt_logger import log_llm_call
        log_llm_call(
            f"slide_generation_batch_{batch_start+1}-{batch_end}",
            system_prompt, user_prompt, response.content, _dur,
            chunks=source_chunks,
            metadata={"batch_size": len(batch_plans), "batch_start": batch_start + 1, "batch_end": batch_end},
        )

        batch_result = parse_llm_json(response.content, required_fields=["slides"])
        slides = batch_result["slides"]

        for i, slide in enumerate(slides):
            slide.setdefault("subtitle", None)
            slide.setdefault("chain_of_thought", "")
            slide.setdefault("key_summary", slide.get("title", ""))
            slide["slide_index"] = batch_start + i + 1
            all_results.append(slide)

        if on_progress:
            on_progress(batch_end, total)

    return all_results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_rag_context(
    source_chunks: list[dict],
    global_slides: list[dict],
    max_total_chars: int = 6000,
) -> str:
    """Format RAG results for the prompt.

    Instead of truncating each chunk individually, we include full chunks
    until the total character budget is exhausted.
    """
    parts = []
    remaining = max_total_chars

    if source_chunks:
        parts.append("Aus Projekt-Quellen:")
        for chunk in source_chunks:
            text = chunk.get("text", "")
            if not text:
                continue
            if len(text) > remaining:
                break
            meta = chunk.get("metadata", {})
            parts.append(f"  [{meta.get('filename', '?')}]: {text}")
            remaining -= len(text)

    if global_slides and remaining > 200:
        parts.append("\nAus frueheren Praesentationen:")
        for slide in global_slides:
            text = slide.get("text", "")
            if not text or len(text) > remaining:
                break
            parts.append(f"  {text}")
            remaining -= len(text)

    return "\n".join(parts)
