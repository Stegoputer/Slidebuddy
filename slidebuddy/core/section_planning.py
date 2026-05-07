"""Slide planning per chapter — single-shot, deterministic, index-based.

Given a chapter (with its assigned source_ids), build an ordered, indexed
pool of source chunks and ask the LLM in one call to produce slide titles,
briefs, template assignments, and explicit `source_indices` referring back
into the pool. Code resolves those indices into concrete chunk text — no
post-hoc vector search per slide, no second blind retrieval pass.

If the model omits or returns invalid indices for a slide, a deterministic
fallback splits the pool sequentially across the slides so the chapter
still has slides backed by content (the same idea as the old full-source
mode, used as a safety net rather than a separate code path).
"""

from __future__ import annotations

import logging
import time as _t

from slidebuddy.config.defaults import load_preferences
from slidebuddy.rag.chunk_pool import PoolChunk, build_chapter_pool, render_pool_block

logger = logging.getLogger(__name__)


def plan_chapter_slides(
    project_id: str,
    chapter: dict,
    language: str,
    source_ids: list[str] | None = None,
    project_override: dict | None = None,
    user_feedback: str | None = None,
) -> dict:
    """Plan a chapter's slides in one LLM call backed by an indexed source pool.

    Args:
        project_id: project ID (used to read chunks from ChromaDB).
        chapter: dict with title, summary, estimated_slide_count, key_topics.
        language: target language ('de' or 'en').
        source_ids: list of source IDs assigned to this chapter. If empty,
            the LLM plans from chapter metadata only and slides receive no
            chunks (the same behaviour you'd get for a chapter with no
            uploaded sources today).
        project_override: optional project-level prompt overrides.
        user_feedback: optional user feedback for iteration.

    Returns:
        Dict with `slides` (list with title, brief, template_type,
        source_indices, chunks) and `reasoning`. Also includes
        `pool_size` and `used_headline_map` for debug/UI.
    """
    from slidebuddy.llm.prompt_assembler import assemble_prompt
    from slidebuddy.llm.router import get_llm

    prefs = load_preferences()
    planning_prefs = prefs.get("planning", {})
    pool_token_budget = int(planning_prefs.get("pool_token_budget", 25000))

    pool, used_map = build_chapter_pool(
        project_id=project_id,
        chapter=chapter,
        source_ids=source_ids or [],
        pool_token_budget=pool_token_budget,
    )

    system_prompt = assemble_prompt(
        phase="section_planning",
        project_override=project_override,
    )

    user_prompt = _build_user_prompt(
        chapter=chapter,
        pool=pool,
        language=language,
        user_feedback=user_feedback,
    )

    llm = get_llm("planning")
    result = _invoke_with_parse_retry(
        llm=llm,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        label="section_planning",
    )

    slides = result.get("slides") if isinstance(result, dict) else None
    if not isinstance(slides, list):
        slides = []

    estimated = max(1, int(chapter.get("estimated_slide_count") or 5))
    if not slides:
        slides = _deterministic_fallback_slides(chapter, pool, estimated)

    _attach_chunks(slides, pool)

    out = {
        "slides": slides,
        "reasoning": result.get("reasoning", "") if isinstance(result, dict) else "",
        "pool_size": len(pool),
        "used_headline_map": used_map,
    }
    return out


# Backwards-compat alias: existing callers (and tests) expect `plan_sections`.
# The chunk_mode / source_texts / extra_chunks parameters are no longer used —
# the function self-fetches and decides on a single deterministic strategy.
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
    return plan_chapter_slides(
        project_id=project_id,
        chapter=chapter,
        language=language,
        source_ids=source_ids,
        project_override=project_override,
        user_feedback=user_feedback,
    )


def _build_user_prompt(
    chapter: dict,
    pool: list[PoolChunk],
    language: str,
    user_feedback: str | None,
) -> str:
    lang_label = "Deutsch" if language == "de" else "English"
    key_topics = ", ".join(chapter.get("key_topics") or []) or "—"
    estimated = max(1, int(chapter.get("estimated_slide_count") or 5))

    parts = [
        f"KAPITEL: {chapter.get('title', '')}",
        f"ZUSAMMENFASSUNG: {chapter.get('summary', '')}",
        f"KERNTHEMEN: {key_topics}",
        f"SPRACHE: {lang_label}",
        f"GEWÜNSCHTE FOLIENANZAHL: {estimated}",
        "",
        "Plane GENAU diese Anzahl Folien. Verteile dabei die Quellinhalte sinnvoll —",
        "jede Folie soll inhaltlich aus dem Pool unten stammen. Erfinde nichts.",
        "",
        "Pro Folie lieferst du:",
        '  - "title": prägnanter Folientitel',
        '  - "brief": 2–3 Sätze, was konkret auf der Folie steht (NICHT generisch)',
        '  - "template_type": passendes Template aus der Liste',
        '  - "source_indices": Liste der Pool-Indizes, die diese Folie inhaltlich abdeckt',
        "",
        "Regeln für source_indices:",
        "  - Jede Folie MUSS mindestens einen Index nennen, sofern der Pool nicht leer ist.",
        "  - Folge möglichst der Reihenfolge der Indizes (roter Faden).",
        "  - Mehrere Folien dürfen denselben Index referenzieren, wenn das Material dicht ist.",
        "  - Verwende NUR Indizes, die im Pool unten existieren (0-basiert).",
        "",
        f"INDEXIERTER QUELLPOOL ({len(pool)} Einträge):",
        "---",
        render_pool_block(pool),
        "---",
    ]

    if user_feedback:
        parts.append(f"\nUSER-FEEDBACK ZUR ÜBERARBEITUNG:\n{user_feedback}")

    return "\n".join(parts)


def _invoke_with_parse_retry(llm, system_prompt: str, user_prompt: str, label: str) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage
    from slidebuddy.llm.invoke_helpers import invoke_with_retry
    from slidebuddy.llm.prompt_logger import log_llm_call
    from slidebuddy.llm.response_parser import parse_llm_json

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
        response = invoke_with_retry(llm, messages, label=label)
        _dur = _t.perf_counter() - _start
        log_llm_call(label, system_prompt, user_prompt, response.content, _dur)

        try:
            return parse_llm_json(response.content, required_fields=["slides"])
        except ValueError as e:
            last_parse_error = str(e)
            logger.warning(
                "Section planning JSON parse failed (attempt %d/2): %s",
                attempt + 1, e,
            )
            if attempt == 1:
                raise

    raise RuntimeError("unreachable")  # pragma: no cover


def _attach_chunks(slides: list[dict], pool: list[PoolChunk]) -> None:
    """Resolve `source_indices` into `chunks` for each slide.

    Three cases:
      1. LLM produced valid indices → resolve them to chunks directly.
      2. LLM produced no/invalid indices but pool is non-empty → assign
         pool chunks sequentially (slide i gets the i-th block of pool
         chunks, computed by splitting [0..pool_size) into N equal parts).
         This guarantees every slide is backed by real source chunks.
      3. Pool is empty → slide.chunks stays empty (chapter has no sources
         in the project at all).
    """
    n = len(slides)

    if not pool:
        for slide in slides:
            slide.setdefault("source_indices", [])
            slide.setdefault("chunks", [])
        return

    pool_size = len(pool)

    for i, slide in enumerate(slides):
        raw = slide.get("source_indices") or []
        valid_idx: list[int] = []
        seen: set[int] = set()
        for v in raw:
            try:
                idx = int(v)
            except (ValueError, TypeError):
                continue
            if 0 <= idx < pool_size and idx not in seen:
                seen.add(idx)
                valid_idx.append(idx)

        if not valid_idx:
            # Sequential fallback: slide i covers a contiguous slice of the pool.
            # `max(start + 1, end)` ensures every slide gets at least one chunk
            # even when n_slides > pool_size (slides at the tail wrap to the last).
            start = (i * pool_size) // n
            end = ((i + 1) * pool_size) // n
            if end <= start:
                # n > pool_size — wrap to a single chunk based on slide index
                valid_idx = [min(pool_size - 1, i)]
            else:
                valid_idx = list(range(start, end))

        slide["source_indices"] = valid_idx
        slide["chunks"] = [_chunk_payload(pool[idx], idx) for idx in valid_idx]


def _chunk_payload(c: PoolChunk, pool_idx: int) -> dict:
    # distance=None signalisiert "kein Vector-Score" — die Zuordnung kam vom
    # LLM per Index, nicht aus Similarity-Search. Die UI nutzt
    # metadata.pool_index, um diese als "LLM-Auswahl" zu labeln statt
    # eine irreführende 100%-Relevanz anzuzeigen.
    return {
        "text": c.text,
        "distance": None,
        "selected": True,
        "metadata": {
            "source_id": c.source_id,
            "filename": c.filename,
            "chunk_index": c.chunk_index,
            "headline": c.headline,
            "pool_index": pool_idx,
        },
    }


def _deterministic_fallback_slides(
    chapter: dict, pool: list[PoolChunk], n_slides: int,
) -> list[dict]:
    """If the LLM returned no slides at all, build a stub plan from the pool."""
    title = chapter.get("title") or "Kapitel"
    if not pool:
        return [{
            "title": f"{title} — Teil {i + 1}",
            "brief": "",
            "template_type": "detail",
            "source_indices": [],
        } for i in range(n_slides)]

    pool_size = len(pool)
    slides: list[dict] = []
    for i in range(n_slides):
        start = (i * pool_size) // n_slides
        end = ((i + 1) * pool_size) // n_slides
        idxs = list(range(start, max(start + 1, end)))
        idxs = [j for j in idxs if 0 <= j < pool_size]
        slides.append({
            "title": f"{title} — Teil {i + 1}",
            "brief": "",
            "template_type": "detail",
            "source_indices": idxs,
        })
    return slides
