"""Chapter planning node — LLM-based chapter structure with integrated gap analysis."""

import logging
import re

from slidebuddy.config.defaults import load_preferences

logger = logging.getLogger(__name__)


def _get_planning_prefs() -> dict:
    """Load planning preferences with defaults."""
    return load_preferences().get("planning", {})


def compute_density_params(total_chars: int, planning_prefs: dict | None = None) -> dict:
    """Derive chapter/slide density from source text length and settings.

    Returns dict with:
        total_chars, max_total_slides, suggested_chapters,
        target_slides_per_chapter, min_slides_per_chapter, max_chapters
    """
    prefs = planning_prefs or _get_planning_prefs()
    min_chars = prefs.get("min_chars_per_slide", 1500)
    target_per_ch = prefs.get("target_slides_per_chapter", 5)
    max_ch = prefs.get("max_chapters", 12)
    min_per_ch = prefs.get("min_slides_per_chapter", 3)

    max_total_slides = max(1, total_chars // min_chars)
    suggested_chapters = max(2, min(max_ch, max_total_slides // max(1, target_per_ch)))

    return {
        "total_chars": total_chars,
        "max_total_slides": max_total_slides,
        "suggested_chapters": suggested_chapters,
        "target_slides_per_chapter": target_per_ch,
        "min_slides_per_chapter": min_per_ch,
        "max_chapters": max_ch,
    }


def plan_chapters(
    project_id: str,
    topic: str,
    language: str,
    source_summaries: list[str],
    project_override: dict | None = None,
    user_feedback: str | None = None,
    density: dict | None = None,
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
    from langchain_core.messages import HumanMessage, SystemMessage
    from slidebuddy.llm.invoke_helpers import invoke_with_retry
    from slidebuddy.llm.prompt_assembler import assemble_prompt
    from slidebuddy.llm.response_parser import parse_llm_json
    from slidebuddy.llm.router import get_llm

    system_prompt = assemble_prompt(
        phase="chapter_planning",
        project_override=project_override,
    )

    # Build user prompt with context
    source_block = _format_source_summaries(source_summaries)
    rag_context = _get_topic_rag_context(project_id, topic, language)

    user_parts = [
        f"THEMA: {topic}",
        f"SPRACHE: {'Deutsch' if language == 'de' else 'English'}",
        f"\nVERFÜGBARE QUELLEN:\n{source_block}" if source_block else "\nKeine Quellen hochgeladen.",
    ]

    if rag_context:
        user_parts.append(f"\nQUELLENÜBERBLICK (Stichproben aus allen hochgeladenen Dateien):\n{rag_context}")

    if density:
        user_parts.append(
            "\nSTRUKTURVORGABEN:"
            f"\n- Ca. {density['suggested_chapters']} Kapitel (maximal {density['max_chapters']})"
            f"\n- Ca. {density['target_slides_per_chapter']} Folien pro Kapitel"
            f"\n- Maximal {density['max_total_slides']} Folien INSGESAMT (nicht pro Kapitel)"
            f"\n- Mindestens {density['min_slides_per_chapter']} Folien pro Kapitel"
        )

    if user_feedback:
        user_parts.append(f"\nUSER-FEEDBACK ZUR ÜBERARBEITUNG:\n{user_feedback}")

    user_prompt = "\n".join(user_parts)

    llm = get_llm("planning")

    import time as _t
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    _start = _t.perf_counter()
    response = invoke_with_retry(llm, messages, label="chapter_planning")
    _dur = _t.perf_counter() - _start

    from slidebuddy.llm.prompt_logger import log_llm_call
    log_llm_call("chapter_planning", system_prompt, user_prompt, response.content, _dur)

    result = parse_llm_json(response.content, required_fields=["chapters"])
    result.setdefault("source_gaps", [])
    return result


def plan_chapters_one_per_source(sources: list) -> dict:
    """Deterministically create one chapter per uploaded source — no LLM, no 500.

    Args:
        sources: List of Source DB objects from get_sources_for_project().

    Returns:
        Dict compatible with plan_chapters() output: chapters, source_gaps,
        total_estimated_slides, reasoning. Each chapter dict also contains
        '_source_id' (internal key, used by router to populate source_ids).
    """
    prefs = _get_planning_prefs()
    min_chars = prefs.get("min_chars_per_slide", 1500)
    min_per_ch = prefs.get("min_slides_per_chapter", 3)

    chapters = []
    for source in sources:
        title = _source_title(source)
        text_len = len((source.original_text or "").strip())

        if text_len > 0:
            slide_estimate = max(min_per_ch, text_len // min_chars)
        else:
            slide_estimate = max(min_per_ch, min(8, (source.chunk_count or 0) // 10 + 3))

        chapters.append({
            "title": title,
            "summary": f"Inhalte aus der Quelle: {source.filename}",
            "estimated_slide_count": slide_estimate,
            "key_topics": [],
            "source_coverage": "good",
            "_source_id": source.id,
        })

    total = sum(c["estimated_slide_count"] for c in chapters)
    return {
        "chapters": chapters,
        "source_gaps": [],
        "total_estimated_slides": total,
        "reasoning": f"Je Quelle ein Kapitel ({len(chapters)} Quellen).",
    }


def plan_chapters_full_source_split(
    sources: list,
    user_feedback: str | None = None,
    language: str = "de",
    project_override: dict | None = None,
    density: dict | None = None,
) -> dict:
    """Split sources into thematic chapters using LLM paragraph tagging.

    The text is split into numbered paragraphs. The LLM sees the full
    numbered paragraph list plus the user's goal and assigns paragraph
    ranges to each chapter — ensuring non-overlapping, complete coverage.

    Falls back to deterministic splitting if the LLM call fails.

    Args:
        sources: List of Source DB objects.
        user_feedback: User's goal/context from the planning prompt modal.
        language: Target language ('de' or 'en').
        project_override: Optional project-level prompt overrides.
        density: Pre-computed density params from compute_density_params().

    Returns:
        Dict compatible with plan_chapters() output.
    """
    from slidebuddy.core.text_utils import number_paragraphs

    # Compute density if not provided
    if not density:
        total_chars = sum(len(s.original_text or "") for s in sources)
        density = compute_density_params(total_chars)

    target_slides_per_chapter = density["target_slides_per_chapter"]

    # Build per-source paragraph maps
    source_paragraphs: list[tuple] = []  # (source, paragraphs_list)
    for source in sources:
        text = source.original_text or ""
        if not text.strip():
            continue
        paras = number_paragraphs(text)
        if paras:
            source_paragraphs.append((source, paras))

    if not source_paragraphs:
        return _fallback_deterministic_split(sources)

    # Try LLM-based chapter planning with paragraph tagging
    try:
        llm_chapters = _llm_plan_chapters(
            source_paragraphs, user_feedback, language, project_override,
            density,
        )
    except Exception as e:
        logger.warning("LLM chapter planning failed (%s), falling back to deterministic split.", e)
        llm_chapters = None

    if not llm_chapters:
        return _fallback_deterministic_split(sources)

    # Build chapters with paragraph-based source segments
    chapters = []
    if len(source_paragraphs) == 1:
        source, paras = source_paragraphs[0]
        n_paras = len(paras)

        # Validate and fix paragraph ranges from LLM
        llm_chapters = _validate_paragraph_ranges(llm_chapters, n_paras)

        for i, llm_ch in enumerate(llm_chapters):
            p_start = max(1, min(llm_ch["paragraph_start"], n_paras))
            p_end = max(p_start, min(llm_ch["paragraph_end"], n_paras))

            seg_start = paras[p_start - 1]["start"]
            seg_end = paras[p_end - 1]["end"]

            chapters.append({
                "title": llm_ch.get("title", f"Kapitel {i + 1}"),
                "summary": llm_ch.get("summary", ""),
                "estimated_slide_count": llm_ch.get("estimated_slide_count", target_slides_per_chapter),
                "key_topics": llm_ch.get("key_topics", []),
                "source_coverage": "good",
                "_source_id": source.id,
                "_source_segment": [seg_start, seg_end],
            })
    else:
        # Multi-source: LLM returns source-prefixed ranges like "S1-1" to "S1-8"
        source_by_idx = {i + 1: sp for i, sp in enumerate(source_paragraphs)}

        for i, llm_ch in enumerate(llm_chapters):
            src_idx = llm_ch.get("source_index", 1)
            if src_idx not in source_by_idx:
                src_idx = min(source_by_idx.keys(), key=lambda k: abs(k - src_idx))
            source, paras = source_by_idx[src_idx]

            p_start = max(1, min(llm_ch.get("paragraph_start", 1), len(paras)))
            p_end = max(p_start, min(llm_ch.get("paragraph_end", len(paras)), len(paras)))

            seg_start = paras[p_start - 1]["start"]
            seg_end = paras[p_end - 1]["end"]

            chapters.append({
                "title": llm_ch.get("title", f"Kapitel {i + 1}"),
                "summary": llm_ch.get("summary", ""),
                "estimated_slide_count": llm_ch.get("estimated_slide_count", target_slides_per_chapter),
                "key_topics": llm_ch.get("key_topics", []),
                "source_coverage": "good",
                "_source_id": source.id,
                "_source_segment": [seg_start, seg_end],
            })

    total = sum(c["estimated_slide_count"] for c in chapters)
    return {
        "chapters": chapters,
        "source_gaps": [],
        "total_estimated_slides": total,
        "reasoning": f"LLM-gestützte Aufteilung in {len(chapters)} Kapitel (Absatz-Tagging).",
    }


def _llm_plan_chapters(
    source_paragraphs: list[tuple],
    user_feedback: str | None,
    language: str,
    project_override: dict | None,
    density: dict,
) -> list[dict]:
    """Ask LLM to create a chapter structure using numbered paragraph tagging.

    The LLM receives all paragraphs numbered and assigns paragraph ranges
    to each chapter, ensuring non-overlapping, complete coverage.
    """
    import time as _t
    from langchain_core.messages import HumanMessage, SystemMessage
    from slidebuddy.llm.invoke_helpers import invoke_with_retry
    from slidebuddy.llm.prompt_assembler import assemble_prompt
    from slidebuddy.llm.response_parser import parse_llm_json
    from slidebuddy.llm.router import get_llm
    from slidebuddy.core.text_utils import format_numbered_paragraphs

    system_prompt = assemble_prompt(
        phase="chapter_planning",
        project_override=project_override,
    )

    lang_label = "Deutsch" if language == "de" else "English"
    is_multi = len(source_paragraphs) > 1

    # Build numbered paragraph block
    if is_multi:
        para_blocks = []
        total_paras = 0
        for i, (source, paras) in enumerate(source_paragraphs, 1):
            prefix = f"S{i}-"
            title = _source_title(source)
            para_blocks.append(f"\n--- Quelle {i}: {title} ---")
            para_blocks.append(format_numbered_paragraphs(paras, source_prefix=prefix))
            total_paras += len(paras)
        numbered_text = "\n".join(para_blocks)
        source_names = ", ".join(
            f"S{i}: {_source_title(s)}" for i, (s, _) in enumerate(source_paragraphs, 1)
        )
    else:
        source, paras = source_paragraphs[0]
        numbered_text = format_numbered_paragraphs(paras)
        total_paras = len(paras)
        source_names = _source_title(source)

    user_parts = [
        "AUFGABE: Erstelle eine Kapitelstruktur fuer eine Praesentation.",
        "Der Quelltext ist in nummerierte Absaetze aufgeteilt.",
        "Ordne jedem Kapitel die thematisch passenden Absaetze zu.",
        "",
        f"SPRACHE: {lang_label}",
        f"QUELLEN: {source_names}",
        f"ANZAHL ABSAETZE: {total_paras}",
        "",
        "STRUKTURVORGABEN:",
        f"- Erstelle ca. {density['suggested_chapters']} Kapitel (maximal {density['max_chapters']})",
        f"- Ca. {density['target_slides_per_chapter']} Folien pro Kapitel",
        f"- Maximal {density['max_total_slides']} Folien insgesamt",
        f"- Mindestens {density['min_slides_per_chapter']} Folien pro Kapitel",
    ]

    if user_feedback:
        user_parts.append(f"\nZIEL DES USERS:\n{user_feedback}")

    user_parts.append(f"\nNUMMERIERTE ABSAETZE:\n{numbered_text}")

    # JSON format instruction depends on single vs multi source
    if is_multi:
        json_format = (
            '{"chapters": [\n'
            '  {"title": "...", "summary": "...", "estimated_slide_count": N,\n'
            '   "source_index": 1, "paragraph_start": 1, "paragraph_end": 8},\n'
            '  ...\n'
            ']}'
        )
        extra_rules = (
            "- source_index: Nummer der Quelle (S1=1, S2=2, ...)\n"
            "- paragraph_start/end beziehen sich auf die Absatz-Nummern INNERHALB dieser Quelle\n"
            "- Ein Kapitel darf nur Absaetze aus EINER Quelle enthalten"
        )
    else:
        json_format = (
            '{"chapters": [\n'
            '  {"title": "...", "summary": "...", "estimated_slide_count": N,\n'
            '   "paragraph_start": 1, "paragraph_end": 8},\n'
            '  ...\n'
            ']}'
        )
        extra_rules = (
            f"- Die Absatz-Bereiche muessen lueckenlos von 1 bis {total_paras} reichen\n"
            "- paragraph_end von Kapitel N muss = paragraph_start - 1 von Kapitel N+1 sein"
        )

    user_parts.append(
        "\nREGELN:\n"
        "- Jedes Kapitel bekommt einen zusammenhaengenden Absatz-Bereich (paragraph_start bis paragraph_end)\n"
        "- Absaetze duerfen NICHT mehreren Kapiteln zugeordnet werden\n"
        "- Der gesamte Text muss abgedeckt sein — keine Absaetze duerfen fehlen\n"
        "- Teile nach inhaltlichen Sinneinheiten, NICHT nach Absatz-Anzahl\n"
        "- Kapitel duerfen sich thematisch NICHT ueberlappen\n"
        f"{extra_rules}\n"
        "\nAntworte NUR als JSON:\n"
        f"{json_format}"
    )

    user_prompt = "\n".join(user_parts)

    llm = get_llm("planning")
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    _start = _t.perf_counter()
    response = invoke_with_retry(llm, messages, label="chapter_planning_full_source")
    _dur = _t.perf_counter() - _start

    from slidebuddy.llm.prompt_logger import log_llm_call
    log_llm_call("chapter_planning_full_source", system_prompt, user_prompt, response.content, _dur)

    result = parse_llm_json(response.content, required_fields=["chapters"])
    chapters = result.get("chapters", [])
    if not chapters:
        raise ValueError("LLM returned empty chapters list")
    return chapters


def _validate_paragraph_ranges(llm_chapters: list[dict], n_paras: int) -> list[dict]:
    """Validate and fix paragraph ranges from LLM response.

    Ensures ranges are:
    - Within bounds (1 to n_paras)
    - Non-overlapping
    - Complete coverage (all paragraphs assigned)

    Falls back to even distribution if validation fails.
    If there are more chapters than paragraphs, excess chapters are dropped.
    """
    # Check if all chapters have valid paragraph_start/end
    valid = True
    for ch in llm_chapters:
        ps = ch.get("paragraph_start")
        pe = ch.get("paragraph_end")
        if not isinstance(ps, int) or not isinstance(pe, int):
            valid = False
            break
        if ps < 1 or pe > n_paras or ps > pe:
            valid = False
            break

    if valid:
        # Check for gaps and overlaps
        sorted_chs = sorted(llm_chapters, key=lambda c: c["paragraph_start"])
        expected_start = 1
        for ch in sorted_chs:
            if ch["paragraph_start"] != expected_start:
                valid = False
                break
            expected_start = ch["paragraph_end"] + 1
        if valid and expected_start - 1 != n_paras:
            valid = False

    if valid:
        return sorted(llm_chapters, key=lambda c: c["paragraph_start"])

    # Fallback: distribute paragraphs evenly across chapters
    # Cap chapter count to n_paras so every chapter gets at least 1 paragraph
    n_chapters = min(len(llm_chapters), n_paras)
    if n_chapters < len(llm_chapters):
        logger.warning(
            "More chapters (%d) than paragraphs (%d) — dropping %d excess chapters.",
            len(llm_chapters), n_paras, len(llm_chapters) - n_chapters,
        )
        llm_chapters = llm_chapters[:n_chapters]

    logger.warning(
        "LLM paragraph ranges invalid (n_paras=%d, n_chapters=%d) — using even distribution.",
        n_paras, n_chapters,
    )
    paras_per = n_paras // n_chapters
    remainder = n_paras % n_chapters
    start = 1
    for i, ch in enumerate(llm_chapters):
        count = paras_per + (1 if i < remainder else 0)
        ch["paragraph_start"] = start
        ch["paragraph_end"] = start + count - 1
        start += count
    return llm_chapters


def _fallback_deterministic_split(sources: list) -> dict:
    """Fallback: deterministic one-chapter-per-source when LLM fails or no text."""
    prefs = _get_planning_prefs()
    min_chars = prefs.get("min_chars_per_slide", 1500)
    min_per_ch = prefs.get("min_slides_per_chapter", 3)

    chapters = []
    for source in sources:
        title = _source_title(source)
        text = source.original_text or ""
        text_len = len(text.strip())
        if text_len > 0:
            total_slides = max(min_per_ch, text_len // min_chars)
        else:
            total_slides = max(min_per_ch, min(8, (source.chunk_count or 0) // 10 + 3))
        chapters.append({
            "title": title,
            "summary": f"Inhalte aus: {source.filename}",
            "estimated_slide_count": total_slides,
            "key_topics": [],
            "source_coverage": "good",
            "_source_id": source.id,
        })
    total = sum(c["estimated_slide_count"] for c in chapters)
    return {
        "chapters": chapters,
        "source_gaps": [],
        "total_estimated_slides": total,
        "reasoning": f"Deterministischer Fallback: {len(chapters)} Kapitel.",
    }


def _source_title(source) -> str:
    """Extract a meaningful title from a source.

    Priority:
    1. YouTube: real video title stored in filename (or short URL fallback).
    2. URL/DOI filenames: extract title from first meaningful line of original_text.
    3. Regular filenames: strip extension + clean underscores/hyphens.
    Fallback: try original_text first line before giving up.
    """
    fn = source.filename or ""

    # --- YouTube ---
    if source.source_type == "youtube":
        if fn.startswith("http"):
            # Legacy: URL stored as filename — extract video ID as label
            return f"YouTube: {fn.split('=')[-1][:40]}" if "=" in fn else f"YouTube: {fn[-40:]}"
        return fn  # Real title from metadata

    # --- Detect URL or DOI as filename (not human-readable) ---
    is_url = fn.startswith(("http://", "https://", "doi:"))
    is_doi = bool(re.match(r"^\d{2}\.\d{4,}/", fn))  # e.g. 10.1038/nature12345
    is_opaque = is_url or is_doi

    # For URL/DOI filenames, always try to extract from content first
    if is_opaque:
        title = _extract_title_from_text(source.original_text or "")
        if title:
            return title
        # Show a short, readable version of the URL/DOI
        if is_doi:
            return f"DOI: {fn[:80]}"
        # URL: strip scheme and show host + path snippet
        clean_url = re.sub(r"^https?://", "", fn)
        return f"Quelle: {clean_url[:70]}" if len(clean_url) > 70 else f"Quelle: {clean_url}"

    # --- Regular filename ---
    base = fn.rsplit(".", 1)[0] if "." in fn else fn
    # Replace underscores and hyphens with spaces for readability
    clean = re.sub(r"[_\-]+", " ", base).strip()
    if clean:
        return clean

    return fn


def _extract_title_from_text(text: str) -> str:
    """Try to extract a title from the first meaningful lines of text.

    Returns the first line that looks like a title (short, no trailing period,
    not a page number or pure number).  Returns "" if nothing suitable is found.
    """
    if not text:
        return ""
    for line in text.splitlines()[:30]:
        line = line.strip()
        if not line:
            continue
        # Skip pure numbers (page numbers, years alone)
        if re.match(r"^\d+\.?$", line):
            continue
        # Skip very short fragments
        if len(line) < 8:
            continue
        # Skip very long lines (paragraph text, not a title)
        if len(line) > 220:
            continue
        # Prefer lines that do NOT end with a period (titles usually don't)
        # but accept them if nothing else fits — handled by early return
        return line[:150]
    return ""


def _format_source_summaries(summaries: list[str]) -> str:
    """Format source summaries for the prompt."""
    if not summaries:
        return ""
    lines = []
    for i, summary in enumerate(summaries, 1):
        lines.append(f"{i}. {summary}")
    return "\n".join(lines)


def _get_topic_rag_context(project_id: str, topic: str, language: str = "de") -> str:
    """Build a sampled overview of all project source chunks.

    Instead of a full RAG search, we evenly sample chunks from each source
    to give the LLM a content overview for chapter planning and gap analysis.
    Uses settings: overview_sample_interval, overview_chars_per_chunk.
    """
    try:
        from slidebuddy.config.defaults import load_preferences
        from slidebuddy.rag.chroma_manager import get_project_sources_collection

        rag = load_preferences().get("rag", {})
        interval = rag.get("overview_sample_interval", 2)
        chars_per = rag.get("overview_chars_per_chunk", 400)

        collection = get_project_sources_collection(project_id)
        count = collection.count()
        if count == 0:
            return ""

        # Fetch all documents + metadata (no embeddings needed)
        data = collection.get(include=["documents", "metadatas"])
        docs = data.get("documents", [])
        metas = data.get("metadatas", [])

        # Group chunks by source filename
        by_source: dict[str, list[tuple[int, str]]] = {}
        for i, (doc, meta) in enumerate(zip(docs, metas)):
            filename = (meta or {}).get("filename", "?")
            chunk_idx = (meta or {}).get("chunk_index", i)
            by_source.setdefault(filename, []).append((chunk_idx, doc or ""))

        # Sort each source by chunk_index, then sample at intervals
        lines = []
        for filename, chunks in sorted(by_source.items()):
            chunks.sort(key=lambda x: x[0])
            n_samples = max(2, len(chunks) // max(1, interval))
            if len(chunks) <= n_samples:
                sampled = chunks
            else:
                step = len(chunks) / n_samples
                sampled = [chunks[int(i * step)] for i in range(n_samples)]

            lines.append(f"Quelle: {filename} ({len(chunks)} Chunks)")
            for idx, text in sampled:
                preview = text[:chars_per].replace("\n", " ")
                lines.append(f"  [Chunk {idx}]: {preview}...")

        return "\n".join(lines)
    except Exception as e:
        logger.warning("Source overview failed (non-critical): %s", e)
        return ""


