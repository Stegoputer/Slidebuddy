"""Export slides to formatted plain text.

Supports two input formats:
- DB slides: list of Slide dataclass instances (content_json as JSON string)
- Draft gen_slides: dict[int, list[dict]] from session state (content as dict)
"""

import json


def export_txt(project_name: str, chapters: list, slides: list) -> str:
    """Export DB slides as formatted text grouped by chapter.

    Args:
        project_name: Project name for the header.
        chapters: List of Chapter dataclass instances or dicts with 'id'/'title'.
        slides: List of Slide dataclass instances or dicts.
    """
    lines = [f"{'=' * 50}", f"  {project_name}", f"{'=' * 50}", ""]

    slide_num = 0
    for chapter in chapters:
        ch_id = chapter.get("id") if isinstance(chapter, dict) else getattr(chapter, "id", "")
        ch_title = chapter.get("title") if isinstance(chapter, dict) else getattr(chapter, "title", "")

        chapter_slides = [s for s in slides if _get(s, "chapter_id") == ch_id]
        if not chapter_slides:
            continue

        lines.append(f"{'─' * 50}")
        lines.append(f"  KAPITEL: {ch_title}")
        lines.append(f"{'─' * 50}")
        lines.append("")

        for slide in chapter_slides:
            slide_num += 1
            lines.extend(_format_slide(slide, slide_num))

    return "\n".join(lines)


def export_gen_slides_txt(
    project_name: str,
    gen_slides: dict[int, list[dict]],
    chapters: list | None = None,
) -> str:
    """Export gen_slides drafts (chapter_idx -> list[dict]) as formatted text.

    Args:
        project_name: Project name for the header.
        gen_slides: Dict mapping chapter index to list of generated slide dicts.
        chapters: Optional list of chapter objects for titles.
    """
    lines = [f"{'=' * 50}", f"  {project_name}", f"{'=' * 50}", ""]

    slide_num = 0
    for ch_idx in sorted(gen_slides.keys()):
        ch_title = _chapter_title(ch_idx, chapters)
        lines.append(f"{'─' * 50}")
        lines.append(f"  KAPITEL {ch_idx + 1}: {ch_title}")
        lines.append(f"{'─' * 50}")
        lines.append("")

        for slide in gen_slides[ch_idx]:
            slide_num += 1
            lines.extend(_format_slide(slide, slide_num))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get(obj, field, default=None):
    """Get field from dict or dataclass."""
    if isinstance(obj, dict):
        return obj.get(field, default)
    return getattr(obj, field, default)


def _chapter_title(ch_idx: int, chapters: list | None) -> str:
    if not chapters or ch_idx >= len(chapters):
        return ""
    ch = chapters[ch_idx]
    return ch.get("title") if isinstance(ch, dict) else getattr(ch, "title", "")


def _format_slide(slide, slide_num: int) -> list[str]:
    """Format a single slide as text lines."""
    lines = []
    template = _get(slide, "template_type", "")
    template_label = template.replace("_", " ").title()
    reuse_marker = " [wiederverwendet]" if _get(slide, "is_reused") else ""

    lines.append(f"{'━' * 50}")
    lines.append(f"FOLIE {slide_num} – {template_label}{reuse_marker}")
    lines.append(f"{'━' * 50}")
    lines.append("")

    title = _get(slide, "title", "")
    subtitle = _get(slide, "subtitle", "")
    if title:
        lines.append(f"TITEL: {title}")
    if subtitle:
        lines.append(f"SUBTITEL: {subtitle}")
    if title or subtitle:
        lines.append("")

    # Content — handle both "content" (gen_slides dict) and "content_json" (DB string)
    raw_content = _get(slide, "content") or _get(slide, "content_json")
    if raw_content:
        try:
            content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
            if isinstance(content, dict):
                lines.append(_format_content(content, template))
            else:
                lines.append(str(content))
        except (json.JSONDecodeError, TypeError):
            lines.append(str(raw_content))
        lines.append("")

    # Speaker notes
    notes = _get(slide, "speaker_notes", "")
    if notes:
        lines.append("SPRECHERNOTIZEN:")
        lines.append(notes)
        lines.append("")

    return lines


def _format_content(content: dict, template_type: str) -> str:
    """Format content dict based on template type."""
    parts = []

    if template_type == "two_column":
        if content.get("left_box"):
            parts.append(f"[LINKS] {content['left_box'].get('heading', '')}")
            parts.append(f"  {content['left_box'].get('text', '')}")
        if content.get("right_box"):
            parts.append(f"[RECHTS] {content['right_box'].get('heading', '')}")
            parts.append(f"  {content['right_box'].get('text', '')}")
        if content.get("conclusion"):
            parts.append(f"\nFAZIT: {content['conclusion']}")

    elif template_type == "numbered":
        for point in content.get("points", []):
            parts.append(f"  {point.get('number', '')}. {point.get('heading', '')}")
            parts.append(f"     {point.get('text', '')}")

    elif template_type == "three_horizontal":
        for col in content.get("columns", []):
            parts.append(f"[{col.get('heading', '')}]")
            parts.append(f"  {col.get('text', '')}")

    elif template_type == "grid":
        for box in content.get("boxes", []):
            parts.append(f"[{box.get('heading', '')}]")
            parts.append(f"  {box.get('text', '')}")

    elif template_type == "detail":
        for section in content.get("sections", []):
            parts.append(f"## {section.get('heading', '')}")
            for bullet in section.get("bullets", []):
                parts.append(f"  - {bullet.get('heading', '')}: {bullet.get('text', '')}")

    elif template_type == "quote":
        parts.append(f'"{content.get("text", "")}"')

    else:
        # Fallback
        for key, val in content.items():
            if isinstance(val, str) and val.strip():
                parts.append(f"  {key}: {val}")

    return "\n".join(parts)
