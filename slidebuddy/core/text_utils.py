"""Shared text utilities for splitting and segmenting source texts."""


def number_paragraphs(
    text: str,
    min_paragraphs: int = 6,
    target_paragraph_chars: int = 500,
) -> list[dict]:
    """Split text into numbered paragraphs with char positions.

    Splitting strategy (in order of preference):
    1. Split on double newlines (\\n\\n)
    2. If too few → split on single newlines (\\n)
    3. If still too few → split on sentence boundaries (. ! ?)

    When sentence splitting produces many tiny fragments, adjacent
    sentences are merged into paragraphs of ~target_paragraph_chars.

    Returns list of dicts, each with:
        index: 1-based paragraph number
        text:  paragraph content (stripped)
        start: start char position in original text
        end:   end char position in original text (exclusive)
    """
    import re

    # Try splitting strategies in order of preference
    for separator in ["\n\n", "\n", None]:
        if separator is not None:
            raw_parts = _split_with_positions(text, separator)
        else:
            # Sentence splitting: split after . ! ? followed by space
            raw_parts = _split_sentences_with_positions(text)

        # Filter empty parts
        parts = [(s, e) for s, e in raw_parts if text[s:e].strip()]

        if len(parts) >= min_paragraphs:
            # If we got too many small parts (e.g. sentence split), merge them
            if len(parts) > 80:
                parts = _merge_short_parts(text, parts, target_paragraph_chars)
            return _build_paragraph_list(text, parts)

    # Last resort: return whatever we have
    return _build_paragraph_list(text, parts)


def _split_with_positions(text: str, separator: str) -> list[tuple[int, int]]:
    """Split text by separator and return (start, end) char positions."""
    parts = []
    pos = 0
    sep_len = len(separator)
    for chunk in text.split(separator):
        start = pos
        end = pos + len(chunk)
        parts.append((start, end))
        pos = end + sep_len
    return parts


def _split_sentences_with_positions(text: str) -> list[tuple[int, int]]:
    """Split text on sentence boundaries and return (start, end) positions."""
    import re
    parts = []
    pos = 0
    for m in re.finditer(r'(?<=[.!?])\s+', text):
        end = m.start() + 1  # include the punctuation
        if end > pos:
            parts.append((pos, end))
        pos = m.end()
    if pos < len(text):
        parts.append((pos, len(text)))
    return parts


def _merge_short_parts(
    text: str,
    parts: list[tuple[int, int]],
    target_chars: int,
) -> list[tuple[int, int]]:
    """Merge adjacent small parts into chunks of ~target_chars."""
    merged = []
    group_start = parts[0][0]
    group_len = 0

    for start, end in parts:
        chunk_len = end - start
        if group_len > 0 and group_len + chunk_len > target_chars:
            # Close current group, start new one
            merged.append((group_start, start))
            group_start = start
            group_len = 0
        group_len += chunk_len

    # Close last group
    if parts:
        merged.append((group_start, parts[-1][1]))

    return merged


def _build_paragraph_list(text: str, parts: list[tuple[int, int]]) -> list[dict]:
    """Convert (start, end) positions to numbered paragraph dicts."""
    paragraphs = []
    for idx, (start, end) in enumerate(parts, 1):
        stripped = text[start:end].strip()
        if stripped:
            paragraphs.append({
                "index": idx,
                "text": stripped,
                "start": start,
                "end": end,
            })
    # Re-number after filtering
    for i, p in enumerate(paragraphs, 1):
        p["index"] = i
    return paragraphs


def format_numbered_paragraphs(paragraphs: list[dict], source_prefix: str = "") -> str:
    """Format paragraphs as numbered list for LLM prompt.

    Args:
        paragraphs: Output of number_paragraphs().
        source_prefix: Optional prefix like "S1-" for multi-source.

    Returns:
        Formatted string like "[S1-1] First paragraph...\\n[S1-2] Second..."
    """
    lines = []
    for p in paragraphs:
        label = f"[{source_prefix}{p['index']}]"
        lines.append(f"{label} {p['text']}")
    return "\n".join(lines)


def split_into_segments(text: str, n: int) -> list[str]:
    """Split text into N roughly equal, sequential segments.

    Tries to break on paragraph boundaries when possible to avoid
    splitting mid-sentence. Falls back to character-based splits if
    paragraphs don't line up evenly.
    """
    if n <= 0:
        return []
    if n == 1:
        return [text.strip()]

    # Prefer splitting on double newlines (paragraphs). Chunks are then
    # distributed into N buckets by cumulative length.
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < n:
        # Not enough paragraphs — fall back to character-based split
        total = len(text)
        return [
            text[(i * total) // n : ((i + 1) * total) // n].strip()
            for i in range(n)
        ]

    # Distribute paragraphs into N buckets balancing by length
    total_len = sum(len(p) for p in paragraphs)
    target = total_len / n
    buckets: list[list[str]] = [[] for _ in range(n)]
    bucket_len = 0.0
    bucket_idx = 0
    for para in paragraphs:
        buckets[bucket_idx].append(para)
        bucket_len += len(para)
        # Advance to next bucket once we've reached the target — but keep the
        # last bucket open so remaining paragraphs land there.
        if bucket_len >= target and bucket_idx < n - 1:
            bucket_idx += 1
            bucket_len = 0.0

    return ["\n\n".join(b).strip() for b in buckets]
