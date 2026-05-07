"""Shared LLM response parser — single place for JSON extraction from LLM output."""

import json
import logging
import re

logger = logging.getLogger(__name__)


def parse_llm_json(content, required_fields: list[str] | None = None) -> dict:
    """Parse JSON from an LLM response, handling common LLM output quirks.

    Handles:
    - Markdown code fences (```json ... ```)
    - Text before/after JSON (e.g. "Here's the result: {...}")
    - Nested JSON extraction when LLM adds commentary
    - LangChain content as either a plain string or a list of content
      blocks (newer Anthropic models return blocks like
      ``[{"type": "text", "text": "..."}]``).

    Args:
        content: Raw LLM response string OR list of content blocks.
        required_fields: Fields that must exist in the parsed dict.

    Returns:
        Parsed dict.

    Raises:
        ValueError: If JSON is invalid or required fields are missing.
    """
    text = _normalize_content_to_text(content).strip()

    # Strategy 1: Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Strategy 2: Try direct parse
    result = _try_parse(text)

    # Strategy 3: Find first { ... } or [ ... ] block
    if result is None:
        result = _extract_json_object(text)

    if result is None:
        logger.error("Failed to parse LLM JSON response: %s", content[:500])
        raise ValueError("LLM-Antwort konnte nicht als JSON geparst werden.")

    # If we got a list, wrap it (some LLMs return bare arrays)
    if isinstance(result, list):
        result = {"slides": result}

    # If we got a single slide dict (no "slides" key but has slide-like fields),
    # wrap it — happens when LLM generates exactly 1 slide and skips the array
    if (
        isinstance(result, dict)
        and "slides" not in result
        and "title" in result
        and "content" in result
    ):
        logger.warning("LLM returned single slide dict instead of slides array — wrapping.")
        result = {"slides": [result]}

    if required_fields:
        for field in required_fields:
            if field not in result:
                raise ValueError(f"LLM-Antwort fehlt Feld '{field}'.")

    return result


def _normalize_content_to_text(content) -> str:
    """Convert LangChain message.content into a plain string.

    Anthropic's modern langchain-anthropic versions return content as a list
    of blocks (e.g. ``[{"type": "text", "text": "..."}]``) for newer Claude
    models, while older versions and most other providers return a plain
    string. We collapse both into a single string so the downstream parser
    can stay simple.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # {"type": "text", "text": "..."} — Anthropic content blocks.
                # Skip non-text blocks (tool_use, image, etc.) since they
                # cannot contribute to a JSON parse.
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif isinstance(block.get("text"), str):
                    parts.append(block["text"])
            else:
                text_attr = getattr(block, "text", None)
                if isinstance(text_attr, str):
                    parts.append(text_attr)
        return "".join(parts)
    return str(content)


def _try_parse(text: str) -> dict | list | None:
    """Try to parse text as JSON, return None on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_json_object(text: str) -> dict | list | None:
    """Find and extract the first JSON object or array from text.

    Handles cases where the LLM writes text before/after the JSON.
    """
    # Find the first { or [
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue

        # Find matching closing bracket by counting depth
        depth = 0
        in_string = False
        escape_next = False

        for i in range(start, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue
            if char == '\\' and in_string:
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue

            if char == start_char:
                depth += 1
            elif char == end_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    result = _try_parse(candidate)
                    if result is not None:
                        return result
                    break

    return None
