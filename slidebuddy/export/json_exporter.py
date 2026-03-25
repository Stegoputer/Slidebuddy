import json
from datetime import datetime


def export_json(project: dict, chapters: list[dict], slides: list[dict]) -> str:
    """Export project as JSON."""
    output = {
        "project": {
            "id": project.get("id", ""),
            "name": project.get("name", ""),
            "language": project.get("language", "de"),
            "created_at": project.get("created_at", datetime.utcnow().isoformat()),
        },
        "chapters": [],
    }

    for chapter in chapters:
        chapter_slides = [s for s in slides if s.get("chapter_id") == chapter.get("id")]
        chapter_slides.sort(key=lambda s: s.get("slide_index_in_chapter", 0))

        chapter_data = {
            "title": chapter.get("title", ""),
            "slides": [],
        }

        for slide in chapter_slides:
            content = slide.get("content_json", "{}")
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    content = {}

            chapter_data["slides"].append({
                "slide_index": slide.get("slide_index", 0),
                "template": slide.get("template_type", ""),
                "is_reused": slide.get("is_reused", False),
                "content": content,
                "speaker_notes": slide.get("speaker_notes", ""),
            })

        output["chapters"].append(chapter_data)

    return json.dumps(output, indent=2, ensure_ascii=False)
