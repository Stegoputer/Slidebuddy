"""Phase 1: Chapter planning UI with HITL — plan, review, iterate.

Supports:
- LLM-based iteration (via feedback prompt)
- Manual inline editing of individual fields
- Per-chapter delete with confirmation
- Drag-style reordering (⬆️⬇️) with confirm/cancel

State persistence: The full chapter plan JSON is stored in the versions
table (state_json) so it survives page navigation and browser refresh.
"""

import json

import streamlit as st

from slidebuddy.config.defaults import DB_PATH
from slidebuddy.core.nodes.chapter_planning import plan_chapters
from slidebuddy.core.progress import delete_steps_after, detect_project_step, get_step_index
from slidebuddy.db.migrations import get_connection
from slidebuddy.db.helpers import save_versioned_state
from slidebuddy.db.models import Chapter, SourceGap
from slidebuddy.db.queries import (
    create_chapter,
    create_source_gap,
    get_chapters_for_project,
    get_project,
    get_sources_for_project,
    get_versions_for_project,
)
from slidebuddy.ui.components.delete_confirm import render_delete_button, render_delete_trigger
from slidebuddy.ui.components.inline_edit import inline_number, inline_text
from slidebuddy.ui.components.reorder import render_reorder
from slidebuddy.ui.components.stepbar import render_stepbar

_PLAN_VERSION_LABEL = "chapter_plan"


def render_chapter_planning():
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

    st.header(f"📋 Kapitelplanung — {project.name}")

    render_stepbar(conn, project_id, "chapters")

    # Clear state when project changes
    if st.session_state.get("chapter_project_id") != project_id:
        st.session_state.chapter_project_id = project_id
        st.session_state.pop("chapter_plan", None)
        st.session_state.pop("chapter_plan_approved", None)
        st.session_state.pop("chapter_feedback", None)

    # Session state init
    if "chapter_feedback" not in st.session_state:
        st.session_state.chapter_feedback = None
    if "chapter_plan" not in st.session_state or st.session_state.chapter_plan is None:
        _load_plan_from_db(conn, project_id)
    if "chapter_plan_approved" not in st.session_state:
        st.session_state.chapter_plan_approved = False

    if st.session_state.get("chapter_plan") is None:
        _render_generate_button(project, conn)
    else:
        _render_chapter_plan(project, conn)

    conn.close()


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

def _load_plan_from_db(conn, project_id: str):
    versions = get_versions_for_project(conn, project_id)
    for v in versions:
        if v.state == _PLAN_VERSION_LABEL and v.state_json:
            try:
                st.session_state.chapter_plan = json.loads(v.state_json)
                st.session_state.chapter_plan_approved = True
                return
            except json.JSONDecodeError:
                pass

    existing_chapters = get_chapters_for_project(conn, project_id)
    if existing_chapters:
        st.session_state.chapter_plan = {
            "chapters": [
                {
                    "title": ch.title,
                    "summary": ch.summary,
                    "estimated_slide_count": ch.estimated_slide_count,
                    "key_topics": [],
                    "source_coverage": "good",
                }
                for ch in existing_chapters
            ],
            "source_gaps": [],
            "total_estimated_slides": sum(ch.estimated_slide_count for ch in existing_chapters),
            "reasoning": "Aus vorheriger Planung geladen.",
        }
        st.session_state.chapter_plan_approved = True
    else:
        st.session_state.chapter_plan = None
        st.session_state.chapter_plan_approved = False


def _save_chapters_to_db(project, conn):
    plan = st.session_state.chapter_plan
    plan["total_estimated_slides"] = sum(
        ch.get("estimated_slide_count", 0) for ch in plan.get("chapters", [])
    )

    conn.execute("DELETE FROM slides WHERE project_id = ?", (project.id,))
    conn.execute("DELETE FROM chapters WHERE project_id = ?", (project.id,))
    conn.execute("DELETE FROM source_gaps WHERE project_id = ?", (project.id,))
    conn.commit()

    for i, ch in enumerate(plan.get("chapters", [])):
        create_chapter(conn, Chapter(
            project_id=project.id,
            chapter_index=i,
            title=ch["title"],
            summary=ch.get("summary", ""),
            estimated_slide_count=ch.get("estimated_slide_count", 5),
            status="planned",
        ))

    for gap in plan.get("source_gaps", []):
        create_source_gap(conn, SourceGap(
            project_id=project.id,
            description=f"[{gap.get('chapter_title', '')}] {gap.get('description', '')}",
            status="open",
        ))

    save_versioned_state(conn, project.id, _PLAN_VERSION_LABEL, -1, plan)


# ---------------------------------------------------------------------------
# LLM generation
# ---------------------------------------------------------------------------

def _render_generate_button(project, conn):
    sources = get_sources_for_project(conn, project.id)
    done_sources = [s for s in sources if s.processing_status == "done"]

    if not done_sources:
        st.warning("Keine verarbeiteten Quellen vorhanden. Bitte zuerst Quellen hochladen.")
        return

    st.info(f"{len(done_sources)} Quelle(n) verfügbar.")

    if st.button("🧠 Kapitelstruktur generieren", type="primary", use_container_width=True):
        _run_chapter_planning(project, done_sources)


def _run_chapter_planning(project, sources, feedback: str | None = None):
    source_summaries = _build_stable_source_summaries(sources)

    with st.spinner("Kapitelstruktur wird generiert..."):
        try:
            result = plan_chapters(
                project_id=project.id,
                topic=project.topic,
                language=project.language,
                source_summaries=source_summaries,
                project_override=project.parsed_override,
                user_feedback=feedback,
            )
            st.session_state.chapter_plan = result
            st.session_state.chapter_plan_approved = False
            st.rerun()
        except Exception as e:
            st.error(f"Fehler bei der Kapitelplanung: {e}")


def _build_stable_source_summaries(sources) -> list[str]:
    summaries = []
    for s in sorted(sources, key=lambda s: s.filename):
        text = (s.original_text or "").strip()
        excerpt = text[:800] if text else "(kein Text extrahiert)"
        summaries.append(f"{s.filename} ({s.source_type}, {s.chunk_count} Chunks):\n{excerpt}")
    return summaries


# ---------------------------------------------------------------------------
# Plan display
# ---------------------------------------------------------------------------

def _render_chapter_plan(project, conn):
    plan = st.session_state.chapter_plan
    chapters = plan.get("chapters", [])
    gaps = plan.get("source_gaps", [])
    is_approved = st.session_state.chapter_plan_approved
    is_reordering = st.session_state.get("ch_reorder_mode", False)

    total = sum(c.get("estimated_slide_count", 0) for c in chapters)
    st.metric("Kapitel", len(chapters), delta=f"~{total} Folien gesamt")

    if plan.get("reasoning"):
        with st.expander("Begründung"):
            st.markdown(plan["reasoning"])

    st.subheader("Kapitelstruktur")

    if is_reordering:
        _render_reorder_mode(chapters)
    else:
        for i, chapter in enumerate(chapters):
            _render_chapter_card(i, chapter, len(chapters), is_approved)

        # Add chapter button
        if not is_approved:
            col_add, col_reorder, col_spacer = st.columns([1, 1, 4])
            with col_add:
                if st.button("➕ Kapitel hinzufügen", use_container_width=True):
                    chapters.append({
                        "title": "Neues Kapitel",
                        "summary": "",
                        "estimated_slide_count": 5,
                        "key_topics": [],
                        "source_coverage": "partial",
                    })
                    st.rerun()
            with col_reorder:
                if len(chapters) > 1 and st.button("↕️ Reihenfolge ändern", use_container_width=True):
                    st.session_state.ch_reorder_mode = True
                    st.session_state.ch_reorder_draft = [ch.copy() for ch in chapters]
                    st.rerun()

    # Source gaps
    if gaps:
        st.subheader("⚠️ Quellen-Lücken")
        for gap in gaps:
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                gap.get("severity", "low"), "⚪"
            )
            st.markdown(
                f"{severity_icon} **{gap.get('chapter_title', '')}**: "
                f"{gap.get('description', '')}"
            )

    st.divider()

    if not is_approved and not is_reordering:
        _render_review_controls(project, conn)
    elif is_approved:
        st.success("Kapitelstruktur freigegeben.")
        if st.button("▶️ Weiter zur Sektionsplanung", type="primary", use_container_width=True):
            st.session_state.current_page = "section_planning"
            st.rerun()

        # Re-plan with warning if subsequent data exists
        _render_replan_button(project, conn)


# ---------------------------------------------------------------------------
# Chapter card with inline edit + delete
# ---------------------------------------------------------------------------

def _render_chapter_card(idx: int, chapter: dict, total: int, is_approved: bool):
    coverage = chapter.get("source_coverage", "")
    coverage_icon = {"good": "🟢", "partial": "🟡", "weak": "🔴"}.get(coverage, "⚪")

    with st.container(border=True):
        st.markdown(f"##### Kapitel {idx + 1} {coverage_icon} {coverage}")

        # Delete confirmation
        if not is_approved:
            confirm_key = f"_ch_confirm_delete_{idx}"

            def _do_delete(_i=idx):
                st.session_state.chapter_plan["chapters"].pop(_i)
                st.session_state.chapter_plan_approved = False

            if render_delete_button(chapter.get("title", ""), confirm_key, f"ch_del_{idx}", _do_delete):
                return

        if is_approved:
            st.markdown(f"**Titel:** {chapter.get('title', '')}")
            st.markdown(f"**Zusammenfassung:** {chapter.get('summary', '')}")
            st.markdown(f"**Folienanzahl:** {chapter.get('estimated_slide_count', '?')}")
            topics = chapter.get("key_topics", [])
            if topics:
                st.caption("Themen: " + " · ".join(topics))
        else:
            def _update_title(val, _i=idx):
                st.session_state.chapter_plan["chapters"][_i]["title"] = val
                st.session_state.chapter_plan_approved = False

            inline_text("Titel", chapter.get("title", ""),
                        key=f"ch_title_{idx}", on_change=_update_title)

            def _update_summary(val, _i=idx):
                st.session_state.chapter_plan["chapters"][_i]["summary"] = val
                st.session_state.chapter_plan_approved = False

            inline_text("Zusammenfassung", chapter.get("summary", ""),
                        key=f"ch_summary_{idx}", multiline=True, on_change=_update_summary)

            def _update_slides(val, _i=idx):
                st.session_state.chapter_plan["chapters"][_i]["estimated_slide_count"] = val
                st.session_state.chapter_plan_approved = False

            inline_number("Folienanzahl", chapter.get("estimated_slide_count", 5),
                          key=f"ch_slides_{idx}", min_value=1, max_value=20,
                          on_change=_update_slides)

            topics = chapter.get("key_topics", [])
            topics_str = ", ".join(topics) if topics else ""

            def _update_topics(val, _i=idx):
                parsed = [t.strip() for t in val.split(",") if t.strip()]
                st.session_state.chapter_plan["chapters"][_i]["key_topics"] = parsed
                st.session_state.chapter_plan_approved = False

            inline_text("Themen", topics_str,
                        key=f"ch_topics_{idx}", on_change=_update_topics)

            # Delete trigger at the bottom of the card
            if total > 1:
                render_delete_trigger(f"_ch_confirm_delete_{idx}", f"ch_del_trigger_{idx}")


# ---------------------------------------------------------------------------
# Reorder mode
# ---------------------------------------------------------------------------

def _render_reorder_mode(chapters: list[dict]):
    """Render chapters in reorder mode using the shared reorder component."""

    def _on_confirm(new_order):
        st.session_state.chapter_plan["chapters"] = new_order
        st.session_state.chapter_plan_approved = False
        st.session_state.ch_reorder_mode = False

    def _on_cancel():
        st.session_state.ch_reorder_mode = False

    render_reorder(
        items=chapters,
        key_prefix="ch_reorder",
        item_label=lambda ch, i: f"Kapitel {i + 1}: {ch.get('title', '')}",
        on_confirm=_on_confirm,
        on_cancel=_on_cancel,
    )


# ---------------------------------------------------------------------------
# Re-plan with data-loss warning
# ---------------------------------------------------------------------------

def _render_replan_button(project, conn):
    """Show 'Kapitelstruktur neu planen' with a warning if subsequent data exists."""
    confirm_key = "_ch_replan_confirm"
    max_step = detect_project_step(conn, project.id)
    has_subsequent = get_step_index(max_step) > get_step_index("chapters")

    if st.session_state.get(confirm_key):
        st.warning(
            "Kapitelstruktur neu planen? Sektionsplaene und generierte Folien "
            "werden dabei geloescht."
        )
        col_yes, col_no, _ = st.columns([1, 1, 4])
        with col_yes:
            if st.button("Ja, neu planen", type="primary", key="ch_replan_yes"):
                # Delete all subsequent steps (sections + generation)
                delete_steps_after(conn, project.id, "chapters")
                # Also delete chapters themselves from DB so _load_plan_from_db won't reload them
                _delete_chapter_data(conn, project.id)
                _do_replan(project.id)
                st.session_state.pop(confirm_key, None)
                st.rerun()
        with col_no:
            if st.button("Abbrechen", key="ch_replan_no"):
                st.session_state.pop(confirm_key, None)
                st.rerun()
    else:
        if st.button("🔄 Kapitelstruktur neu planen"):
            if has_subsequent:
                st.session_state[confirm_key] = True
                st.rerun()
            else:
                _delete_chapter_data(conn, project.id)
                _do_replan(project.id)
                st.rerun()


def _delete_chapter_data(conn, project_id: str):
    """Remove chapter plan and chapters from DB so re-planning starts fresh."""
    conn.execute("DELETE FROM source_gaps WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM chapters WHERE project_id = ?", (project_id,))
    conn.execute(
        "DELETE FROM versions WHERE project_id = ? AND state = ?",
        (project_id, _PLAN_VERSION_LABEL),
    )
    conn.commit()


def _do_replan(project_id: str = ""):
    """Reset chapter plan state for re-planning."""
    st.session_state.chapter_plan = None
    st.session_state.chapter_plan_approved = False
    st.session_state.pop("section_plans", None)
    st.session_state.pop("sections_approved", None)
    st.session_state.pop("gen_slides", None)
    st.session_state.pop("gen_chapter_idx", None)
    st.session_state.pop("gen_all_done", None)
    if project_id:
        st.session_state.pop(f"_stepbar_max_{project_id}", None)


# ---------------------------------------------------------------------------
# Review controls
# ---------------------------------------------------------------------------

def _render_review_controls(project, conn):
    col_approve, col_iterate = st.columns(2)

    with col_approve:
        if st.button("✅ Freigeben", type="primary", use_container_width=True):
            _save_chapters_to_db(project, conn)
            st.session_state.chapter_plan_approved = True
            st.rerun()

    with col_iterate:
        if st.button("🔄 Per LLM überarbeiten", use_container_width=True):
            st.session_state.chapter_feedback = ""
            st.rerun()

    if st.session_state.chapter_feedback is not None:
        feedback = st.text_area(
            "Was soll das LLM ändern?",
            placeholder="z.B. 'Kapitel 2 und 3 zusammenführen' oder 'Praxisbeispiele hinzufügen'",
        )
        if st.button("Feedback senden") and feedback:
            st.session_state.chapter_feedback = None
            sources = get_sources_for_project(conn, project.id)
            done_sources = [s for s in sources if s.processing_status == "done"]
            _run_chapter_planning(project, done_sources, feedback=feedback)
