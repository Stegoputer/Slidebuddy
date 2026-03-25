"""Analyze a PowerPoint master file and extract layout structures.

Parses each slide layout to extract placeholder names, types, positions,
and generates a structured description that an LLM can use to suggest
template names, descriptions, and generation prompts.
"""

import json
import re

from pptx import Presentation


def analyze_master(file_path: str) -> list[dict]:
    """Parse a PPTX master and return structured layout info.

    Returns a list of dicts, one per layout:
    {
        "layout_index": int,
        "layout_name": str,
        "placeholders": [
            {
                "idx": int,
                "name": str,
                "type": str,       # TITLE, BODY, PICTURE, OBJECT
                "is_content": bool, # True for fillable text/image placeholders
                "position": {"left": float, "top": float},  # inches
                "size": {"width": float, "height": float},  # inches
            }
        ],
        "content_placeholders": [...],  # Only fillable ones (TITLE, BODY, PICTURE)
        "structure_summary": str,       # Human-readable summary
    }
    """
    prs = Presentation(file_path)
    layouts = []

    for i, layout in enumerate(prs.slide_layouts):
        placeholders = []
        for ph in layout.placeholders:
            ph_type = str(ph.placeholder_format.type).split("(")[0].strip()
            # Map enum to readable name
            type_map = {
                "TITLE (1)": "TITLE",
                "BODY (2)": "BODY",
                "PICTURE (18)": "PICTURE",
                "OBJECT (7)": "OBJECT",
            }
            readable_type = type_map.get(str(ph.placeholder_format.type), str(ph.placeholder_format.type))

            placeholders.append({
                "idx": ph.placeholder_format.idx,
                "name": ph.name,
                "type": readable_type,
                "is_content": readable_type in ("TITLE", "BODY", "PICTURE"),
                "position": {
                    "left": round(ph.left / 914400, 2),
                    "top": round(ph.top / 914400, 2),
                },
                "size": {
                    "width": round(ph.width / 914400, 2),
                    "height": round(ph.height / 914400, 2),
                },
            })

        content_phs = [p for p in placeholders if p["is_content"]]

        # Build human-readable summary
        summary_parts = []
        title_phs = [p for p in content_phs if p["type"] == "TITLE"]
        body_phs = [p for p in content_phs if p["type"] == "BODY"]
        image_phs = [p for p in content_phs if p["type"] == "PICTURE"]
        if title_phs:
            summary_parts.append(f"{len(title_phs)} Titel")
        if body_phs:
            names = [p["name"] for p in body_phs]
            summary_parts.append(f"{len(body_phs)} Textfelder ({', '.join(names)})")
        if image_phs:
            summary_parts.append(f"{len(image_phs)} Bilder")

        layouts.append({
            "layout_index": i,
            "layout_name": layout.name,
            "placeholders": placeholders,
            "content_placeholders": content_phs,
            "structure_summary": " | ".join(summary_parts) if summary_parts else "Leer",
        })

    return layouts


def generate_template_key(layout_name: str) -> str:
    """Generate a valid template key from layout name."""
    key = layout_name.lower().strip()
    # Replace German umlauts
    key = key.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    # Replace non-alphanumeric with underscore
    key = re.sub(r"[^a-z0-9]+", "_", key)
    key = key.strip("_")
    return key or "unknown"


def build_content_schema(content_placeholders: list[dict]) -> dict:
    """Build a JSON content schema from the content placeholders.

    Skips TITLE (goes to top-level title) and PICTURE (user inserts manually).
    Only includes text-fillable placeholders.
    """
    schema = {}
    for ph in content_placeholders:
        field_name = ph["name"]
        if ph["type"] == "TITLE":
            continue
        elif ph["type"] == "PICTURE":
            # Images are inserted manually by the user — skip
            continue
        else:
            schema[field_name] = "str — Textinhalt"
    return schema


def build_generation_prompt(
    layout_name: str,
    content_placeholders: list[dict],
    content_schema: dict,
) -> str:
    """Build a generation prompt that matches the prompt_assembler format.

    Produces HINWEISE text that tells the LLM exactly how to fill the content
    JSON for this layout, referencing the actual placeholder field names.
    """
    # Classify placeholders
    body_phs = [p for p in content_placeholders if p["type"] == "BODY"]
    image_phs = [p for p in content_placeholders if p["type"] == "PICTURE"]
    title_phs = [p for p in content_placeholders if p["type"] == "TITLE"]

    # Detect structural patterns
    subheading_phs = [p for p in body_phs if "subheading" in p["name"].lower() or "heading" in p["name"].lower()]
    text_phs = [p for p in body_phs if "text" in p["name"].lower() and "subheading" not in p["name"].lower() and "heading" not in p["name"].lower()]
    bullet_phs = [p for p in body_phs if "bullet" in p["name"].lower()]
    quote_phs = [p for p in body_phs if "quote" in p["name"].lower() or "statement" in p["name"].lower()]
    conclusion_phs = [p for p in body_phs if "conclusion" in p["name"].lower() or "fazit" in p["name"].lower()]
    person_phs = [p for p in body_phs if "person" in p["name"].lower()]
    bridge_phs = [p for p in body_phs if "bridge" in p["name"].lower()]

    lines = []

    # Slide purpose — derive a purpose hint from the layout type
    purpose_map = {
        "zitat": "ein praegnantes Zitat oder eine These wirkungsvoll praesentieren",
        "quote": "ein praegnantes Zitat oder eine These wirkungsvoll praesentieren",
        "vergleich": "zwei oder mehr Aspekte gegenueberstellen und Unterschiede herausarbeiten",
        "comparison": "zwei oder mehr Aspekte gegenueberstellen und Unterschiede herausarbeiten",
        "timeline": "eine chronologische Abfolge oder Entwicklung darstellen",
        "erklaer": "einen Sachverhalt verstaendlich erklaeren und Kernpunkte hervorheben",
        "agenda": "die Gliederung oder naechsten Schritte uebersichtlich auflisten",
        "start": "das Thema einleiten und Interesse wecken",
        "end": "die wichtigsten Erkenntnisse zusammenfassen und einen Ausblick geben",
        "schluss": "die wichtigsten Erkenntnisse zusammenfassen und einen Ausblick geben",
        "team": "Personen oder Rollen vorstellen",
        "statistik": "Zahlen und Daten verstaendlich visualisieren",
        "chart": "Zahlen und Daten verstaendlich visualisieren",
    }
    layout_lower = layout_name.lower()
    purpose = next(
        (desc for keyword, desc in purpose_map.items() if keyword in layout_lower),
        "eine klare Kernaussage vermitteln",
    )
    lines.append(f"- ZIEL dieser \"{layout_name}\"-Folie: {purpose}. Formuliere zuerst intern das Ziel, bevor du die Felder befuellst.")

    # Count repeating groups (e.g. subheading1+text1, subheading2+text2)
    num_groups = max(len(subheading_phs), len(text_phs), 1)
    has_groups = len(subheading_phs) > 1 or len(text_phs) > 1

    # General structure hint
    if has_groups:
        lines.append(f"- Dieses Layout hat {num_groups} inhaltliche Abschnitte die parallel befuellt werden muessen")

    # Field-specific hints (text only — images are ignored)
    if subheading_phs and text_phs:
        lines.append("- Jeder Abschnitt hat eine Ueberschrift (subheading, 2-5 Woerter) und einen Fliesstext (text, 1-3 Saetze)")
        lines.append("- Alle Abschnitte sollten ungefaehr gleich lang sein")
        lines.append("- Ueberschriften sollten parallel formuliert sein (gleicher Satzbau)")

    if bullet_phs:
        lines.append(f"- {len(bullet_phs)} Stichpunkt-Felder — jedes mit einem praegnanten Satz fuellen")

    if quote_phs:
        lines.append("- Zitatfeld mit einem aussagekraeftigen Zitat oder These fuellen")

    if person_phs:
        lines.append("- Personenfeld mit Name und ggf. Rolle/Titel fuellen")

    if conclusion_phs:
        lines.append("- Fazit/Conclusion-Feld mit einer zusammenfassenden Kernaussage fuellen (1 Satz)")

    if bridge_phs:
        lines.append("- Bridge-Feld verbindet die Abschnitte thematisch (kurzer Uebergangssatz)")

    # JSON output reminder — only text fields (no images)
    schema_fields = list(content_schema.keys())
    if schema_fields:
        field_list = ", ".join(f'"{f}"' for f in schema_fields[:8])
        if len(schema_fields) > 8:
            field_list += f" ... ({len(schema_fields)} Felder gesamt)"
        lines.append(f"- Dein JSON-content muss exakt diese Felder enthalten: {field_list}")
        lines.append("- Verwende NUR die genannten Feldnamen, keine eigenen erfinden")
        if image_phs:
            lines.append(f"- {len(image_phs)} Bildplatzhalter vorhanden — diese werden vom Nutzer manuell befuellt, NICHT im JSON ausgeben")

    # Fallback if nothing was detected
    if len(lines) <= 1:
        lines.append("- Befuelle alle Felder im JSON-Schema mit passendem Inhalt")
        lines.append("- Halte Texte praegnant und passend zum Folienthema")

    return "\n".join(lines)


def build_llm_analysis_prompt(layouts: list[dict]) -> str:
    """Build a prompt for LLM to analyze layouts and suggest template metadata."""
    layout_descriptions = []
    for layout in layouts:
        if not layout["content_placeholders"]:
            continue  # Skip empty layouts

        phs = []
        for ph in layout["content_placeholders"]:
            phs.append(f"  - {ph['name']} ({ph['type']}, {ph['size']['width']:.1f}x{ph['size']['height']:.1f} Zoll)")

        layout_descriptions.append(
            f"Layout {layout['layout_index']}: \"{layout['layout_name']}\"\n"
            f"Placeholders:\n" + "\n".join(phs)
        )

    layouts_text = "\n\n".join(layout_descriptions)

    return f"""Analysiere die folgenden PowerPoint-Folienlayouts und erstelle fuer jedes Layout:

1. **display_name**: Ein kurzer, klarer deutscher Name (z.B. "Vergleich Links/Rechts")
2. **description**: 1-2 Saetze Beschreibung wofuer das Layout ideal ist
3. **generation_prompt**: Ein Prompt-Absatz (3-5 Saetze) der dem LLM erklaert wie Content fuer dieses Layout generiert werden soll. Beschreibe welche Felder befuellt werden muessen und wie der Inhalt strukturiert sein soll.

LAYOUTS:

{layouts_text}

Antworte als JSON-Array. Jedes Element hat:
{{
    "layout_index": int,
    "display_name": "str",
    "description": "str",
    "generation_prompt": "str"
}}

Ueberspringe leere Layouts (ohne Content-Placeholders).
Antworte NUR mit dem JSON-Array, ohne Markdown-Fences."""
