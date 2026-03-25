"""Text chunking for RAG ingestion.

Uses a separator hierarchy: headings → paragraphs → sentences.
Oversized paragraphs are split by sentence so no chunk exceeds the limit.
"""

import re
from typing import Optional

# Sentence boundary regex — handles ". ", "! ", "? " and German „..." patterns
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ\"„\'])")

# Default target: ~500 tokens ≈ 2000 chars.  Max hard limit = 2× target.
DEFAULT_CHUNK_SIZE = 500
DEFAULT_OVERLAP = 50


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict]:
    """Split text into chunks with overlap.

    Returns list of {"text": str, "chunk_index": int}.
    Guarantees no chunk exceeds ~2× chunk_size tokens.
    """
    if not text.strip():
        return []

    # Split by paragraphs (double newline)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Explode any oversized paragraphs into sentence-level pieces
    pieces = _split_oversized(paragraphs, chunk_size)

    # Greedily merge pieces into chunks up to chunk_size
    chunks: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0

    for piece in pieces:
        piece_tokens = _estimate_tokens(piece)

        # If adding this piece would exceed the limit, flush current chunk
        if current_tokens + piece_tokens > chunk_size and current_parts:
            chunks.append("\n\n".join(current_parts))

            # Keep overlap from end of current chunk
            overlap_text = _get_overlap(current_parts, overlap)
            current_parts = [overlap_text] if overlap_text else []
            current_tokens = _estimate_tokens(overlap_text) if overlap_text else 0

        current_parts.append(piece)
        current_tokens += piece_tokens

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return [{"text": c, "chunk_index": i} for i, c in enumerate(chunks)]


def chunk_slide(title: str, content: str, speaker_notes: str) -> str:
    """Create a single chunk from a slide for RAG ingestion."""
    parts = []
    if title:
        parts.append(title)
    if content:
        parts.append(content)
    if speaker_notes:
        parts.append(f"---\nSPRECHERNOTIZEN:\n{speaker_notes}")
    return "\n\n".join(parts)


def _estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token for German/English."""
    return len(text) // 4


def _split_oversized(paragraphs: list[str], max_tokens: int) -> list[str]:
    """Split paragraphs that exceed max_tokens into sentence-level pieces.

    Small paragraphs pass through unchanged.  Oversized ones are split by
    sentence boundaries, then greedily merged so each piece stays under the
    limit.  As a last resort, hard-split on whitespace.
    """
    result: list[str] = []
    for para in paragraphs:
        if _estimate_tokens(para) <= max_tokens:
            result.append(para)
            continue

        # Split into sentences
        sentences = _SENTENCE_RE.split(para)

        # Merge sentences greedily into pieces ≤ max_tokens
        current = []
        current_tokens = 0
        for sent in sentences:
            sent_tokens = _estimate_tokens(sent)

            if sent_tokens > max_tokens:
                # Sentence itself is oversized — hard-split by words
                if current:
                    result.append(" ".join(current))
                    current, current_tokens = [], 0
                result.extend(_hard_split(sent, max_tokens))
                continue

            if current_tokens + sent_tokens > max_tokens and current:
                result.append(" ".join(current))
                current, current_tokens = [], 0

            current.append(sent)
            current_tokens += sent_tokens

        if current:
            result.append(" ".join(current))

    return result


def _hard_split(text: str, max_tokens: int) -> list[str]:
    """Last-resort split: break text on word boundaries to fit max_tokens."""
    words = text.split()
    pieces: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for word in words:
        word_tokens = _estimate_tokens(word) + 1  # +1 for space
        if current_tokens + word_tokens > max_tokens and current:
            pieces.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(word)
        current_tokens += word_tokens

    if current:
        pieces.append(" ".join(current))
    return pieces


def _get_overlap(paragraphs: list[str], target_tokens: int) -> Optional[str]:
    """Get text from end of paragraph list for overlap."""
    overlap_parts: list[str] = []
    tokens = 0
    for para in reversed(paragraphs):
        para_tokens = _estimate_tokens(para)
        if tokens + para_tokens > target_tokens and overlap_parts:
            break
        overlap_parts.insert(0, para)
        tokens += para_tokens
    return "\n\n".join(overlap_parts) if overlap_parts else None
