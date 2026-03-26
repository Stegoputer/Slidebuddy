"""Folienmaster management page — import, analyze, and configure PPTX masters."""

import json

import streamlit as st

from slidebuddy.config.defaults import DB_PATH, DATA_DIR, load_preferences
from slidebuddy.core.master_analyzer import (
    analyze_master,
    build_content_schema,
    build_generation_prompt,
    build_llm_analysis_prompt,
    estimate_text_capacity,
    generate_template_key,
)
from slidebuddy.db.migrations import get_connection
from slidebuddy.db.models import MasterTemplate, SlideMaster
from slidebuddy.db.queries import (
    create_master_template,
    create_slide_master,
    delete_slide_master,
    get_active_master_templates,
    get_all_slide_masters,
    get_slide_master,
    get_templates_for_master,
    set_active_slide_master,
    update_master_template,
)
from slidebuddy.llm.response_parser import parse_llm_json

MASTERS_DIR = DATA_DIR / "masters"


def render_slide_masters():
    st.header("Folienmaster")
    st.caption("Importiere einen PowerPoint-Folienmaster um eigene Layouts zu nutzen.")

    # Show persistent warnings from previous import
    if "_master_import_warning" in st.session_state:
        st.warning(st.session_state.pop("_master_import_warning"))

    conn = get_connection(DB_PATH)

    # Upload section
    _render_upload(conn)

    st.divider()

    # List existing masters
    _render_master_list(conn)

    conn.close()


# ---------------------------------------------------------------------------
# Upload and analysis
# ---------------------------------------------------------------------------

def _render_upload(conn):
    st.subheader("Neuen Folienmaster importieren")

    with st.expander("Anleitung: Placeholder-Benennung in PowerPoint", expanded=False):
        st.markdown("""
Damit SlideBuddy die Textfelder korrekt erkennt, muessen die Placeholder in PowerPoint **beschreibend benannt** werden.

**So geht's:** `Ansicht → Folienmaster → Placeholder anklicken → Auswahlbereich (Alt+F10) → Name aendern`

| Namenskonvention | Bedeutung | Beispiel |
|---|---|---|
| `title_placeholder` | Folientitel | Hauptueberschrift |
| `subheading1_placeholder` | Zwischenueberschrift | Abschnitt-Titel (2-5 Woerter) |
| `text1_placeholder` | Fliesstext | Inhaltlicher Abschnitt (Saetze) |
| `bulletpoint1_placeholder` | Stichpunkt | Ein einzelner Aufzaehlungspunkt |
| `quote1_placeholder` | Zitat | Praegnantes Zitat oder These |
| `statement_placeholder` | Statement | Zentrale Aussage |
| `person1_placeholder` | Person | Name + Rolle/Titel |
| `conclusion_placeholder` | Fazit | Zusammenfassender Satz |
| `bridge_placeholder` | Ueberleitung | Verbindung zwischen Abschnitten |
| `image1_placeholder` | Bild | Wird vom Nutzer manuell eingefuegt |
| `count1_placeholder` | Zaehler | Nummerierung (z.B. "01") |

**Nummerierung:** Bei mehreren Feldern gleichen Typs: `text1_placeholder`, `text2_placeholder`, `text3_placeholder`

**Wichtig:** Generische Namen wie `Content Placeholder 2` fuehren zu schlechteren Ergebnissen — das LLM kann nicht erkennen, ob es ein Titel, Fliesstext oder Zitat ist.
""")

    uploaded = st.file_uploader(
        "PowerPoint-Datei (.pptx) hochladen",
        type=["pptx"],
        key="master_upload",
    )

    if uploaded:
        # Show preview info
        st.info(f"Datei: **{uploaded.name}** ({uploaded.size / 1024:.0f} KB)")

        master_name = st.text_input(
            "Name fuer diesen Master",
            value=uploaded.name.replace(".pptx", ""),
            key="master_name_input",
        )

        if st.button("Analysieren und importieren", type="primary", key="import_master_btn"):
            # Prevent double-import on rerun
            if st.session_state.get("_master_importing"):
                return
            st.session_state["_master_importing"] = True
            try:
                _import_master(conn, uploaded, master_name)
            finally:
                st.session_state.pop("_master_importing", None)


def _import_master(conn, uploaded_file, name: str):
    """Save the file, analyze layouts, call LLM for suggestions, save to DB."""
    # Save file — use unique name if file already exists (may be locked)
    MASTERS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = MASTERS_DIR / uploaded_file.name
    if file_path.exists():
        stem = file_path.stem
        suffix = file_path.suffix
        counter = 1
        while file_path.exists():
            file_path = MASTERS_DIR / f"{stem}_{counter}{suffix}"
            counter += 1
    file_path.write_bytes(uploaded_file.getbuffer())

    with st.spinner("Layouts werden analysiert..."):
        layouts = analyze_master(str(file_path))

    # Filter out empty layouts
    content_layouts = [l for l in layouts if l["content_placeholders"]]

    if not content_layouts:
        st.error("Keine nutzbaren Layouts gefunden.")
        return

    st.success(f"{len(content_layouts)} Layouts mit Content gefunden.")

    # Create master in DB
    master = SlideMaster(
        name=name,
        filename=uploaded_file.name,
        file_path=str(file_path),
        is_active=False,
    )
    create_slide_master(conn, master)

    # Call LLM for analysis
    with st.spinner("LLM analysiert Layout-Strukturen..."):
        llm_suggestions = _get_llm_suggestions(content_layouts)

    # Build suggestion lookup
    suggestion_map = {}
    if llm_suggestions:
        for s in llm_suggestions:
            suggestion_map[s.get("layout_index")] = s

    # Create templates for each layout
    for layout in content_layouts:
        idx = layout["layout_index"]
        suggestion = suggestion_map.get(idx, {})
        content_schema = build_content_schema(layout["content_placeholders"])

        # Always build a deterministic generation prompt from placeholder structure
        auto_prompt = build_generation_prompt(
            layout["layout_name"],
            layout["content_placeholders"],
            content_schema,
        )
        # Prepend LLM-generated purpose if available
        purpose = suggestion.get("purpose", "")
        if purpose:
            auto_prompt = f'- ZIEL dieser "{layout["layout_name"]}"-Folie: {purpose}\n' + auto_prompt
        # Append LLM-generated hints
        llm_prompt = suggestion.get("generation_prompt", "")
        if llm_prompt:
            generation_prompt = auto_prompt + "\n" + llm_prompt
        else:
            generation_prompt = auto_prompt

        tpl = MasterTemplate(
            master_id=master.id,
            layout_index=idx,
            layout_name=layout["layout_name"],
            template_key=generate_template_key(layout["layout_name"]),
            display_name=suggestion.get("display_name", layout["layout_name"]),
            description=suggestion.get("description", layout["structure_summary"]),
            placeholder_schema=json.dumps(
                [{
                    "name": p["name"],
                    "type": p["type"],
                    "idx": p["idx"],
                    "size": p["size"],
                    "text_capacity": estimate_text_capacity(p),
                } for p in layout["content_placeholders"]],
                ensure_ascii=False,
            ),
            content_schema=json.dumps(content_schema, ensure_ascii=False),
            generation_prompt=generation_prompt,
        )
        create_master_template(conn, tpl)

    st.success(f"Master '{name}' mit {len(content_layouts)} Templates importiert!")
    st.rerun()


def _get_llm_suggestions(layouts: list[dict]) -> list[dict] | None:
    """Call LLM to get display_name, description, purpose, prompt suggestions."""
    try:
        from slidebuddy.llm.router import get_llm
        llm = get_llm("master_analysis")
        prompt = build_llm_analysis_prompt(layouts)
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Try to parse as JSON array
        content = content.strip()
        if content.startswith("```"):
            # Strip markdown fences
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        result = json.loads(content)
        if isinstance(result, list):
            return result
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"LLM master analysis failed: {e}")
        st.session_state["_master_import_warning"] = f"LLM-Analyse fehlgeschlagen: {e}. Verwende Standard-Werte."
        return None


# ---------------------------------------------------------------------------
# Master list and editing
# ---------------------------------------------------------------------------

def _render_master_list(conn):
    masters = get_all_slide_masters(conn)

    if not masters:
        st.info("Noch keine Folienmaster importiert. Der Default-Templatekatalog wird verwendet.")
        return

    # Active master selector
    st.subheader("Aktiver Folienmaster")
    active_options = ["Default (eingebaute Templates)"] + [m.name for m in masters]
    active_ids = [None] + [m.id for m in masters]

    current_active = next((i for i, m in enumerate(masters) if m.is_active), -1)
    current_selection = current_active + 1 if current_active >= 0 else 0

    selected_idx = st.selectbox(
        "Welcher Master soll verwendet werden?",
        range(len(active_options)),
        index=current_selection,
        format_func=lambda i: active_options[i],
        key="active_master_select",
    )

    if st.button("Aktivieren", key="activate_master"):
        set_active_slide_master(conn, active_ids[selected_idx])
        # Clear cached template definitions so new master is used
        from slidebuddy.llm.prompt_assembler import clear_template_cache
        clear_template_cache()
        # Invalidate section plans + generated slides — they use old template keys
        st.session_state.pop("section_plans", None)
        st.session_state.pop("sections_approved", None)
        st.session_state.pop("gen_slides", None)
        st.session_state.pop("gen_chapter_idx", None)
        st.session_state.pop("gen_all_done", None)
        st.success("Aktiver Master geaendert! Sektionsplaene und Folien muessen neu generiert werden.")
        st.rerun()

    st.divider()

    # Show each master with its templates
    for master in masters:
        _render_master_detail(conn, master)


def _render_master_detail(conn, master: SlideMaster):
    active_marker = " ✅" if master.is_active else ""
    with st.expander(f"📐 {master.name}{active_marker} ({master.filename})", expanded=master.is_active):
        templates = get_templates_for_master(conn, master.id)

        if not templates:
            st.info("Keine Templates vorhanden.")
        else:
            for tpl in templates:
                _render_template_editor(conn, tpl)

        # Delete master
        st.divider()
        if st.button(f"Master '{master.name}' loeschen", key=f"del_master_{master.id}"):
            from pathlib import Path
            file_path = Path(master.file_path)
            try:
                if file_path.exists():
                    file_path.unlink()
            except PermissionError:
                pass  # File locked — DB record is removed, file cleaned up later
            delete_slide_master(conn, master.id)
            st.rerun()


def _render_template_editor(conn, tpl: MasterTemplate):
    """Render an editable template card."""
    active_icon = "✅" if tpl.is_active else "⬜"
    with st.container(border=True):
        col_header, col_toggle = st.columns([5, 1])
        with col_header:
            st.markdown(f"**{active_icon} Layout {tpl.layout_index}: {tpl.display_name}**")
            st.caption(f"Key: `{tpl.template_key}` | Original: {tpl.layout_name}")
        with col_toggle:
            new_active = st.checkbox(
                "Aktiv",
                value=tpl.is_active,
                key=f"tpl_active_{tpl.id}",
                label_visibility="collapsed",
            )

        # Show placeholder structure
        if tpl.placeholder_schema:
            try:
                phs = json.loads(tpl.placeholder_schema)
                ph_text = " | ".join(f"`{p['name']}` ({p['type']})" for p in phs)
                st.caption(f"Placeholders: {ph_text}")
            except json.JSONDecodeError:
                pass

        # Editable fields
        new_display_name = st.text_input(
            "Anzeigename",
            value=tpl.display_name,
            key=f"tpl_name_{tpl.id}",
        )
        new_description = st.text_area(
            "Beschreibung",
            value=tpl.description or "",
            key=f"tpl_desc_{tpl.id}",
            height=68,
        )

        # Content schema
        with st.expander("Content-Schema (JSON)"):
            schema_str = tpl.content_schema or "{}"
            try:
                schema_obj = json.loads(schema_str)
                formatted = json.dumps(schema_obj, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                formatted = schema_str
            new_schema = st.text_area(
                "Schema",
                value=formatted,
                key=f"tpl_schema_{tpl.id}",
                height=150,
            )

        # Generation prompt
        with st.expander("Generierungs-Prompt"):
            new_prompt = st.text_area(
                "Prompt",
                value=tpl.generation_prompt or "",
                key=f"tpl_prompt_{tpl.id}",
                height=150,
            )

        # Chat-based refinement
        with st.expander("Per Chat nachbessern"):
            feedback = st.text_input(
                "Was soll angepasst werden?",
                key=f"tpl_chat_{tpl.id}",
                placeholder="z.B. 'Mache die Beschreibung ausfuehrlicher' oder 'Prompt soll mehr auf Stichpunkte achten'",
            )
            if st.button("Anpassen", key=f"tpl_chat_btn_{tpl.id}") and feedback:
                _refine_template_with_llm(conn, tpl, feedback)

        # Save button
        if st.button("Aenderungen speichern", key=f"tpl_save_{tpl.id}"):
            tpl.display_name = new_display_name
            tpl.description = new_description
            tpl.content_schema = new_schema
            tpl.generation_prompt = new_prompt
            tpl.is_active = new_active
            update_master_template(conn, tpl)
            st.success("Gespeichert!")


def _refine_template_with_llm(conn, tpl: MasterTemplate, feedback: str):
    """Use LLM to refine template metadata based on user feedback."""
    try:
        from slidebuddy.llm.router import get_llm
        llm = get_llm("planning")

        prompt = f"""Passe die folgenden Template-Metadaten basierend auf dem Nutzer-Feedback an.

AKTUELL:
- Display-Name: {tpl.display_name}
- Beschreibung: {tpl.description}
- Generierungs-Prompt: {tpl.generation_prompt}
- Content-Schema: {tpl.content_schema}
- Layout-Name: {tpl.layout_name}

FEEDBACK: {feedback}

Antworte als JSON:
{{
    "display_name": "str",
    "description": "str",
    "generation_prompt": "str"
}}

Aendere nur was das Feedback verlangt, behalte den Rest bei.
Antworte NUR mit dem JSON, ohne Markdown-Fences."""

        with st.spinner("LLM arbeitet..."):
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            result = parse_llm_json(content)

            if result.get("display_name"):
                tpl.display_name = result["display_name"]
            if result.get("description"):
                tpl.description = result["description"]
            if result.get("generation_prompt"):
                tpl.generation_prompt = result["generation_prompt"]

            update_master_template(conn, tpl)
            st.success("Template angepasst!")
            st.rerun()
    except Exception as e:
        st.error(f"Fehler: {e}")
