"""Phase 2: Section planning UI — per-chapter slide plans with template assignment.

Supports:
- LLM-based iteration (via feedback prompt)
- Manual inline editing of template type and brief
- Per-slide delete with confirmation
- Reordering slides with confirm/cancel
- Persistent storage via versions table (survives refresh)
"""

import json

import streamlit as st

from slidebuddy.config.defaults import DB_PATH, get_available_template_types
from slidebuddy.core.nodes.section_planning import plan_sections
from slidebuddy.core.progress import delete_steps_after, detect_project_step, get_step_index
from slidebuddy.db.helpers import load_versioned_states, save_versioned_state
from slidebuddy.db.migrations import get_connection
from slidebuddy.db.queries import (
    get_chapters_for_project,
    get_project,
)
from slidebuddy.rag.retrieval import search_project_sources
from slidebuddy.ui.components.delete_confirm import render_delete_button, render_delete_trigger
from slidebuddy.ui.components.inline_edit import inline_select, inline_text
from slidebuddy.ui.components.rag_context import render_chunk_search
from slidebuddy.ui.components.reorder import render_reorder
from slidebuddy.ui.components.stepbar import render_stepbar

_SECTION_VERSION_PREFIX = "section_plan"


def render_section_planning():
    project_id = st.session_state.get("current_project_id")
    if not project_id:
        st.warning("Kein Projekt ausgewählt.")
        return

    conn = get_connection(DB_PATH)
    project = get_project(conn, project_id)
    if not project:
        st.error("Projekt nicht gefunden.")
        conn.close()
        return

    chapters_db = get_chapters_for_project(conn, project_id)

    if not chapters_db:
        conn.close()
        st.warning("Keine Kapitel vorhanden. Bitte zuerst Kapitelplanung durchführen.")
        if st.button("← Zurück zur Kapitelplanung"):
            st.session_state.current_page = "chapter_planning"
            st.rerun()
        return

    st.header(f"📐 Sektionsplanung — {project.name}")

    render_stepbar(conn, project_id, "sections")

    # Clear state when project changes
    if st.session_state.get("section_project_id") != project_id:
        st.session_state.section_project_id = project_id
        st.session_state.pop("section_plans", None)
        st.session_state.pop("sections_approved", None)
        st.session_state.pop("section_feedback", None)

    chapter_plan = st.session_state.get("chapter_plan", {})
    chapters = _build_chapter_list(chapters_db, chapter_plan)

    # Load persisted section plans if session state is empty
    if "section_plans" not in st.session_state or not st.session_state.section_plans:
        _load_section_plans_from_db(conn, project_id)
    if "sections_approved" not in st.session_state:
        st.session_state.sections_approved = False
    if "section_feedback" not in st.session_state:
        st.session_state.section_feedback = {}

    tab_labels = [f"Kap. {i+1}: {ch['title']}" for i, ch in enumerate(chapters)]
    tabs = st.tabs(tab_labels)

    all_planned = True
    for i, (tab, chapter) in enumerate(zip(tabs, chapters)):
        with tab:
            plan = st.session_state.section_plans.get(i)

            if plan:
                _render_section_plan(project, chapter, i, plan, conn)
            else:
                all_planned = False
                _render_plan_button(project, chapter, i, conn)

    st.divider()
    if all_planned and not st.session_state.sections_approved:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Alle Sektionspläne freigeben", type="primary", use_container_width=True):
                st.session_state.sections_approved = True
                _save_all_section_plans(conn, project_id)
                st.rerun()
        with col2:
            if st.button("🔄 Alle neu generieren", use_container_width=True):
                max_step = detect_project_step(conn, project_id)
                has_slides = get_step_index(max_step) > get_step_index("sections")
                if has_slides:
                    st.session_state["_sec_regen_confirm"] = True
                    st.rerun()
                else:
                    _do_regen_all(conn, project_id)
                    st.rerun()

    # Confirmation dialog for re-generating when slides exist
    if st.session_state.get("_sec_regen_confirm"):
        st.warning("Alle Sektionsplaene neu generieren? Generierte Folien werden dabei geloescht.")
        col_yes, col_no, _ = st.columns([1, 1, 4])
        with col_yes:
            if st.button("Ja, neu generieren", type="primary", key="sec_regen_yes"):
                delete_steps_after(conn, project_id, "sections")
                _do_regen_all(conn, project_id)
                st.session_state.pop("_sec_regen_confirm", None)
                st.rerun()
        with col_no:
            if st.button("Abbrechen", key="sec_regen_no"):
                st.session_state.pop("_sec_regen_confirm", None)
                st.rerun()

    if st.session_state.sections_approved:
        st.success("Alle Sektionspläne freigegeben.")
        if st.button("▶️ Weiter zur Slide-Generierung", type="primary", use_container_width=True):
            st.session_state.current_page = "slide_generation"
            st.rerun()

    conn.close()


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

def _version_label(chapter_idx: int) -> str:
    return f"{_SECTION_VERSION_PREFIX}_{chapter_idx}"


def _load_section_plans_from_db(conn, project_id: str):
    """Restore section plans from the versions table."""
    st.session_state.section_plans = load_versioned_states(conn, project_id, _SECTION_VERSION_PREFIX)
    if st.session_state.section_plans:
        st.session_state.sections_approved = True


def _save_section_plan(conn, project_id: str, chapter_idx: int, plan: dict):
    """Persist a single chapter's section plan."""
    save_versioned_state(conn, project_id, _version_label(chapter_idx), chapter_idx, plan)


def _save_all_section_plans(conn, project_id: str):
    """Persist all section plans."""
    for idx, plan in st.session_state.section_plans.items():
        _save_section_plan(conn, project_id, idx, plan)


def _do_regen_all(conn, project_id: str):
    """Clear all section plans and related generation state."""
    st.session_state.section_plans = {}
    st.session_state.pop("gen_slides", None)
    st.session_state.pop("gen_chapter_idx", None)
    st.session_state.pop("gen_all_done", None)
    _delete_all_section_plans(conn, project_id)


def _delete_all_section_plans(conn, project_id: str):
    """Remove all persisted section plans."""
    conn.execute(
        "DELETE FROM versions WHERE project_id = ? AND state LIKE ?",
        (project_id, f"{_SECTION_VERSION_PREFIX}_%"),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_chapter_list(chapters_db, chapter_plan: dict) -> list[dict]:
    plan_chapters = {ch["title"]: ch for ch in chapter_plan.get("chapters", [])}
    result = []
    for ch in chapters_db:
        plan_ch = plan_chapters.get(ch.title, {})
        result.append({
            "id": ch.id,
            "title": ch.title,
            "summary": ch.summary,
            "estimated_slide_count": ch.estimated_slide_count,
            "key_topics": plan_ch.get("key_topics", []),
            "chapter_index": ch.chapter_index,
        })
    return result


_TEMPLATE_ICONS = {
    "title": "📌", "two_column": "📊", "numbered": "🔢",
    "three_horizontal": "📏", "grid": "⬜", "detail": "📝", "quote": "💬",
    # Common master template patterns
    "startfolie": "📌", "erklaerfolie": "📝", "vergleichsfolie": "📊",
    "timelinefolie": "📏", "zitatfolie": "💬", "teamfolie": "👥",
    "statistikfolie": "📈", "bildfolie": "🖼️", "abschlussfolie": "🏁",
}


def _get_template_icon(template_type: str) -> str:
    if template_type in _TEMPLATE_ICONS:
        return _TEMPLATE_ICONS[template_type]
    # Fuzzy match — check if any known keyword appears in the template name
    lower = template_type.lower()
    for key, icon in _TEMPLATE_ICONS.items():
        if key in lower:
            return icon
    return "📄"


# ---------------------------------------------------------------------------
# LLM generation
# ---------------------------------------------------------------------------

def _auto_attach_chunks(project_id: str, chapter_title: str, plan: dict):
    """Auto-retrieve relevant RAG chunks for each slide in a plan."""
    from slidebuddy.config.defaults import load_preferences
    rag = load_preferences().get("rag", {})
    n_per_slide = rag.get("n_chunks_per_slide", 3)
    for slide in plan.get("slides", []):
        query = f"{chapter_title} {slide.get('brief', '')}"
        results = search_project_sources(project_id, query, n_results=n_per_slide)
        slide["chunks"] = [{**chunk, "selected": True} for chunk in results]


def _render_plan_button(project, chapter: dict, chapter_idx: int, conn):
    st.info(
        f"**{chapter['title']}** — {chapter.get('estimated_slide_count', '?')} Folien geplant."
    )
    if st.button("🧠 Folienplan generieren", key=f"gen_section_{chapter_idx}", use_container_width=True):
        _run_section_planning(project, chapter, chapter_idx, conn)


def _run_section_planning(project, chapter: dict, chapter_idx: int, conn, feedback: str | None = None):
    with st.spinner(f"Folienplan fuer '{chapter['title']}' wird erstellt..."):
        try:
            result = plan_sections(
                project_id=project.id,
                chapter=chapter,
                language=project.language,
                project_override=project.parsed_override,
                user_feedback=feedback,
            )
            _auto_attach_chunks(project.id, chapter["title"], result)
            st.session_state.section_plans[chapter_idx] = result
            st.session_state.sections_approved = False
            # Persist immediately
            _save_section_plan(conn, project.id, chapter_idx, result)
            st.rerun()
        except Exception as e:
            st.error(f"Fehler: {e}")


# ---------------------------------------------------------------------------
# Section plan display with inline editing + delete + reorder
# ---------------------------------------------------------------------------

def _render_section_plan(project, chapter: dict, chapter_idx: int, plan: dict, conn):
    slides = plan.get("slides", [])
    is_approved = st.session_state.sections_approved
    reorder_key = f"sec_reorder_mode_{chapter_idx}"
    is_reordering = st.session_state.get(reorder_key, False)

    st.markdown(f"**{len(slides)} Folien geplant**")

    if plan.get("reasoning"):
        with st.expander("Begründung"):
            st.markdown(plan["reasoning"])

    if is_reordering:
        _render_slide_reorder(chapter_idx, slides, conn, project.id)
    else:
        for j, slide in enumerate(slides):
            _render_slide_card(chapter_idx, j, slide, len(slides), is_approved, conn, project.id)

        if not is_approved:
            col_add, col_reorder, _ = st.columns([1, 1, 4])
            with col_add:
                if st.button("➕ Folie hinzufügen", key=f"add_slide_{chapter_idx}", use_container_width=True):
                    available_types = get_available_template_types()
                    slides.append({
                        "template_type": available_types[0] if available_types else "numbered",
                        "brief": "Neue Folie",
                        "reused_slide_id": None,
                        "chunks": [],
                    })
                    _save_section_plan(conn, project.id, chapter_idx, plan)
                    st.rerun()
            with col_reorder:
                if len(slides) > 1 and st.button("↕️ Reihenfolge", key=f"reorder_sec_{chapter_idx}", use_container_width=True):
                    st.session_state[reorder_key] = True
                    st.session_state[f"sec_reorder_draft_{chapter_idx}"] = [s.copy() for s in slides]
                    st.rerun()

            st.divider()

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ OK", key=f"approve_sec_{chapter_idx}", use_container_width=True):
                    pass
            with col2:
                if st.button("🔄 Per LLM neu generieren", key=f"regen_sec_{chapter_idx}", use_container_width=True):
                    st.session_state.section_feedback[chapter_idx] = ""
                    st.rerun()

            if chapter_idx in st.session_state.section_feedback:
                feedback = st.text_area(
                    "Was soll das LLM aendern?",
                    key=f"sec_fb_{chapter_idx}",
                    placeholder="z.B. 'Mehr Vergleichsfolien' oder 'Quote-Folie am Ende'",
                )
                if st.button("Feedback senden", key=f"sec_fb_btn_{chapter_idx}") and feedback:
                    del st.session_state.section_feedback[chapter_idx]
                    _run_section_planning(project, chapter, chapter_idx, conn, feedback=feedback)


def _render_slide_card(chapter_idx: int, slide_idx: int, slide: dict, total: int, is_approved: bool, conn, project_id: str):
    """Render a single slide plan with inline edit + delete."""
    template = slide.get("template_type", "?")
    template_icon = _get_template_icon(template)
    reuse = " ♻️" if slide.get("reused_slide_id") else ""

    with st.container(border=True):
        st.markdown(f"**Folie {slide_idx + 1}**{reuse}")

        # Delete confirmation
        if not is_approved:
            confirm_key = f"_sec_confirm_delete_{chapter_idx}_{slide_idx}"

            def _do_delete(_ci=chapter_idx, _si=slide_idx):
                st.session_state.section_plans[_ci]["slides"].pop(_si)
                st.session_state.sections_approved = False
                _save_section_plan(conn, project_id, _ci, st.session_state.section_plans[_ci])

            if render_delete_button(f"Folie {slide_idx + 1}", confirm_key, f"sec_del_{chapter_idx}_{slide_idx}", _do_delete):
                return

        if is_approved:
            st.caption(f"{template_icon} {template}")
            st.markdown(slide.get("brief", ""))
        else:
            def _update_template(val, _ci=chapter_idx, _si=slide_idx):
                st.session_state.section_plans[_ci]["slides"][_si]["template_type"] = val
                st.session_state.sections_approved = False

            inline_select(
                "Template", template,
                options=get_available_template_types(),
                key=f"sec_tmpl_{chapter_idx}_{slide_idx}",
                on_change=_update_template,
            )

            def _update_brief(val, _ci=chapter_idx, _si=slide_idx):
                st.session_state.section_plans[_ci]["slides"][_si]["brief"] = val
                st.session_state.sections_approved = False

            inline_text(
                "Inhalt", slide.get("brief", ""),
                key=f"sec_brief_{chapter_idx}_{slide_idx}",
                multiline=True,
                on_change=_update_brief,
            )

            # Per-slide chunk management
            _render_slide_chunks(chapter_idx, slide_idx, slide, project_id, conn)

            # Delete trigger at the bottom of the card
            if total > 1:
                render_delete_trigger(f"_sec_confirm_delete_{chapter_idx}_{slide_idx}", f"sec_del_trigger_{chapter_idx}_{slide_idx}")


# ---------------------------------------------------------------------------
# Per-slide chunk management
# ---------------------------------------------------------------------------

def _render_slide_chunks(chapter_idx: int, slide_idx: int, slide: dict, project_id: str, conn):
    """Render chunk selection UI inside a slide card."""
    chunks = slide.get("chunks", [])
    selected_count = sum(1 for c in chunks if c.get("selected", True))
    label = f"Quellen ({selected_count}/{len(chunks)})" if chunks else "Quellen (0)"

    with st.expander(label, expanded=False):
        if chunks:
            for ci, chunk in enumerate(chunks):
                meta = chunk.get("metadata", {})
                filename = meta.get("filename", "?")
                distance = chunk.get("distance")
                dist_label = f" | Relevanz: {1 - distance:.0%}" if distance is not None else ""
                chars = len(chunk.get("text", ""))

                with st.container(border=True):
                    # Header row: checkbox + filename + stats + remove
                    col_cb, col_info, col_rm = st.columns([0.5, 5, 0.5])
                    with col_cb:
                        cb_key = f"chunk_sel_{chapter_idx}_{slide_idx}_{ci}"
                        new_val = st.checkbox(
                            "sel", value=chunk.get("selected", True),
                            key=cb_key, label_visibility="collapsed",
                        )
                        if new_val != chunk.get("selected", True):
                            slide["chunks"][ci]["selected"] = new_val
                            _save_section_plan(conn, project_id, chapter_idx,
                                               st.session_state.section_plans[chapter_idx])
                    with col_info:
                        st.caption(f"**{filename}** (Chunk {meta.get('chunk_index', '?')}){dist_label} | {chars} Zeichen")
                    with col_rm:
                        if st.button("X", key=f"chunk_rm_{chapter_idx}_{slide_idx}_{ci}"):
                            slide["chunks"].pop(ci)
                            _save_section_plan(conn, project_id, chapter_idx,
                                               st.session_state.section_plans[chapter_idx])
                            st.rerun()

                    # Editable chunk text
                    ta_key = f"chunk_text_{chapter_idx}_{slide_idx}_{ci}"
                    edited = st.text_area(
                        "Chunk-Text",
                        value=chunk.get("text", ""),
                        height=120,
                        key=ta_key,
                        label_visibility="collapsed",
                    )
                    if edited != chunk.get("text", ""):
                        slide["chunks"][ci]["text"] = edited
                        _save_section_plan(conn, project_id, chapter_idx,
                                           st.session_state.section_plans[chapter_idx])
        else:
            st.caption("Keine Chunks zugeordnet.")

        # Search and add new chunks
        def _add_chunk(chunk, _ci=chapter_idx, _si=slide_idx):
            target = st.session_state.section_plans[_ci]["slides"][_si]
            if "chunks" not in target:
                target["chunks"] = []
            existing_texts = {c["text"] for c in target["chunks"]}
            if chunk["text"] not in existing_texts:
                target["chunks"].append({**chunk, "selected": True})
                _save_section_plan(conn, project_id, _ci,
                                   st.session_state.section_plans[_ci])

        render_chunk_search(project_id, f"slide_rag_{chapter_idx}_{slide_idx}", on_add=_add_chunk)


# ---------------------------------------------------------------------------
# Slide reorder mode
# ---------------------------------------------------------------------------

def _render_slide_reorder(chapter_idx: int, slides: list[dict], conn, project_id: str):
    """Render slide reorder using the shared reorder component."""

    def _on_confirm(new_order, _ci=chapter_idx):
        st.session_state.section_plans[_ci]["slides"] = new_order
        st.session_state.sections_approved = False
        st.session_state[f"sec_reorder_mode_{_ci}"] = False
        _save_section_plan(conn, project_id, _ci, st.session_state.section_plans[_ci])

    def _on_cancel(_ci=chapter_idx):
        st.session_state[f"sec_reorder_mode_{_ci}"] = False

    render_reorder(
        items=slides,
        key_prefix=f"sec_reorder_{chapter_idx}",
        item_label=lambda s, i: f"{_get_template_icon(s.get('template_type', ''))} {s.get('brief', '')[:80]}",
        on_confirm=_on_confirm,
        on_cancel=_on_cancel,
    )
