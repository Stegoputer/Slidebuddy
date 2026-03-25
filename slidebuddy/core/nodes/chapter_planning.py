"""Chapter planning node — LLM-based chapter structure with integrated gap analysis."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from slidebuddy.llm.prompt_assembler import assemble_prompt
from slidebuddy.llm.response_parser import parse_llm_json
from slidebuddy.llm.router import get_llm
from slidebuddy.rag.retrieval import search_project_sources

logger = logging.getLogger(__name__)


def plan_chapters(
    project_id: str,
    topic: str,
    language: str,
    source_summaries: list[str],
    project_override: dict | None = None,
    user_feedback: str | None = None,
) -> dict:
    """Plan chapter structure with integrated source gap analysis.

    Args:
        project_id: Project ID for RAG queries.
        topic: Presentation topic.
        language: Target language ('de' or 'en').
        source_summaries: List of source filename + excerpt pairs.
        project_override: Optional project-level prompt overrides.
        user_feedback: Optional user feedback for iteration.

    Returns:
        Dict with 'chapters', 'source_gaps', 'total_estimated_slides', 'reasoning'.
    """
    system_prompt = assemble_prompt(
        phase="chapter_planning",
        project_override=project_override,
    )

    # Build user prompt with context
    source_block = _format_source_summaries(source_summaries)
    rag_context = _get_topic_rag_context(project_id, topic)

    user_parts = [
        f"THEMA: {topic}",
        f"SPRACHE: {'Deutsch' if language == 'de' else 'English'}",
        f"\nVERFÜGBARE QUELLEN:\n{source_block}" if source_block else "\nKeine Quellen hochgeladen.",
    ]

    if rag_context:
        user_parts.append(f"\nEXISTIERENDE SLIDES AUS FRÜHEREN PRÄSENTATIONEN:\n{rag_context}")

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
    log_llm_call("chapter_planning", system_prompt, user_prompt, response.content, _dur)

    result = parse_llm_json(response.content, required_fields=["chapters"])
    result.setdefault("source_gaps", [])
    return result


def _format_source_summaries(summaries: list[str]) -> str:
    """Format source summaries for the prompt."""
    if not summaries:
        return ""
    lines = []
    for i, summary in enumerate(summaries, 1):
        lines.append(f"{i}. {summary}")
    return "\n".join(lines)


def _get_topic_rag_context(project_id: str, topic: str) -> str:
    """Search RAG for existing slides related to the topic."""
    from slidebuddy.rag.retrieval import search_global_slides

    hits = search_global_slides(topic, n_results=3)
    if not hits:
        return ""

    lines = []
    for hit in hits:
        meta = hit.get("metadata", {})
        lines.append(
            f"- [{meta.get('project_name', '?')}] {hit['text'][:200]}..."
        )
    return "\n".join(lines)


