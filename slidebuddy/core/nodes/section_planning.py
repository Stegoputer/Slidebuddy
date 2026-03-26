"""Section planning node — detailed slide plans with template assignment per chapter."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from slidebuddy.config.defaults import load_preferences
from slidebuddy.llm.prompt_assembler import assemble_prompt
from slidebuddy.llm.response_parser import parse_llm_json
from slidebuddy.llm.router import get_llm
from slidebuddy.rag.retrieval import search_all

logger = logging.getLogger(__name__)


def plan_sections(
    project_id: str,
    chapter: dict,
    language: str,
    project_override: dict | None = None,
    user_feedback: str | None = None,
    extra_chunks: list[dict] | None = None,
) -> dict:
    """Plan detailed slide structure for a single chapter.

    Args:
        project_id: Project ID for RAG queries.
        chapter: Dict with 'title', 'summary', 'estimated_slide_count', 'key_topics'.
        language: Target language.
        project_override: Optional project-level prompt overrides.
        user_feedback: Optional user feedback for iteration.

    Returns:
        Dict with 'slides' (list of slide plans) and 'reasoning'.
    """
    system_prompt = assemble_prompt(
        phase="section_planning",
        project_override=project_override,
    )

    # RAG: both searches run in parallel via threads
    rag = load_preferences().get("rag", {})
    query = f"{chapter['title']} {chapter.get('summary', '')} {' '.join(chapter.get('key_topics', []))}"
    source_chunks, rag_slides = search_all(
        project_id, query, language=language,
        n_sources=rag.get("n_sources_planning", 5),
        n_global=rag.get("n_global_planning", 3),
    )

    user_parts = [
        f"KAPITEL: {chapter['title']}",
        f"ZUSAMMENFASSUNG: {chapter.get('summary', '')}",
        f"GESCHÄTZTE FOLIENANZAHL: {chapter.get('estimated_slide_count', 5)}",
        f"KERNTHEMEN: {', '.join(chapter.get('key_topics', []))}",
    ]

    # Merge auto-retrieved + manually pinned chunks (pinned first for priority)
    all_source_chunks = list(extra_chunks or []) + source_chunks
    # Deduplicate by text
    seen_texts: set[str] = set()
    unique_chunks: list[dict] = []
    for c in all_source_chunks:
        if c["text"] not in seen_texts:
            seen_texts.add(c["text"])
            unique_chunks.append(c)

    if unique_chunks:
        source_text = "\n".join(
            f"- [{c.get('metadata', {}).get('filename', '?')}]: {c['text'][:150]}..."
            for c in unique_chunks
        )
        user_parts.append(f"\nRELEVANTE QUELLEN:\n{source_text}")

    if rag_slides:
        reuse_text = "\n".join(
            f"- ID: {s['metadata'].get('slide_id', '?')} | {s['text'][:150]}..."
            for s in rag_slides
        )
        user_parts.append(f"\nWIEDERVERWENDBARE SLIDES:\n{reuse_text}")

    if user_feedback:
        user_parts.append(f"\nUSER-FEEDBACK ZUR ÜBERARBEITUNG:\n{user_feedback}")

    user_prompt = "\n".join(user_parts)

    llm = get_llm("planning")

    import time as _t
    _start = _t.perf_counter()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    _dur = _t.perf_counter() - _start

    from slidebuddy.llm.prompt_logger import log_llm_call
    log_llm_call(
        "section_planning", system_prompt, user_prompt, response.content, _dur,
        chunks=unique_chunks,
    )

    return parse_llm_json(response.content, required_fields=["slides"])
