"""Phase 3: Slide generation UI — batch generation with single-slide option."""

import json
import time

import streamlit as st

from slidebuddy.config.defaults import (
    DB_PATH,
    TEXT_LENGTHS,
    load_preferences,
)
from slidebuddy.core.nodes.slide_generation import (
    generate_slide,
    generate_slides_batch,
)
from slidebuddy.core.progress import detect_project_step
from slidebuddy.db.migrations import get_connection
from slidebuddy.db.helpers import load_versioned_states, save_versioned_state
from slidebuddy.db.models import Slide, Version
from slidebuddy.db.queries import (
    create_slide,
    get_chapters_for_project,
    get_project,
    update_chapter_status,
)
from slidebuddy.export.pptx_exporter import export_pptx
from slidebuddy.export.txt_exporter import export_gen_slides_txt
from slidebuddy.ui.components.rag_context import render_rag_chunks
from slidebuddy.ui.components.slide_card import render_slide_card
from slidebuddy.ui.components.stepbar import render_stepbar

_GEN_DRAFT_PREFIX = "gen_slides_"


def render_slide_generation():
    _t = [time.perf_counter()]  # timing checkpoints
    def _mark(label):
        _t.append(time.perf_counter())
        return label

    project_id = st.session_state.get("current_project_id")
    if not project_id:
        st.warning("Kein Projekt ausgewaehlt.")
        return

    conn = get_connection(DB_PATH)
    project = get_project(conn, project_id)
    _mark("1_get_project")
    if not project:
        st.error("Projekt nicht gefunden.")
        conn.close()
        return

    chapters_db = get_chapters_for_project(conn, project_id)
    _mark("2_get_chapters")
    if not chapters_db:
        st.warning("Keine Kapitel vorhanden.")
        conn.close()
        return

    st.header(f"Slide-Generierung — {project.name}")
    _mark("3_header")

    render_stepbar(conn, project_id, "generation")
    _mark("4_stepbar")

    # State initialization — clear and reload when project changes
    if st.session_state.get("gen_project_id") != project_id:
        st.session_state.gen_project_id = project_id
        st.session_state.pop("gen_slides", None)
        st.session_state.pop("gen_chapter_idx", None)
        st.session_state.pop("gen_all_done", None)
        st.session_state.pop("section_plans", None)
        st.session_state.pop("_pptx_cache", None)
        st.session_state.pop("_txt_cache", None)

    if "gen_slides" not in st.session_state or not st.session_state.gen_slides:
        _load_gen_slides_from_db(conn, project_id)
    _mark("5_load_gen_slides")

    if "gen_chapter_idx" not in st.session_state:
        st.session_state.gen_chapter_idx = _detect_current_chapter_idx(chapters_db)
    if "gen_all_done" not in st.session_state:
        st.session_state.gen_all_done = False

    if "section_plans" not in st.session_state or not st.session_state.section_plans:
        _load_section_plans_from_db(conn, project_id)
    _mark("6_load_section_plans")

    section_plans = st.session_state.get("section_plans", {})

    _render_progress_overview(chapters_db)
    _mark("7_progress_overview")

    st.divider()

    if st.session_state.gen_all_done:
        _render_completion(project, chapters_db, conn)
        _mark("8_completion")
    else:
        current_idx = st.session_state.gen_chapter_idx
        if current_idx < len(chapters_db):
            chapter = chapters_db[current_idx]
            section_plan = section_plans.get(current_idx, {})
            _render_chapter_generation(project, chapter, current_idx, section_plan, chapters_db, conn)
            _mark("8_chapter_gen")
        else:
            st.session_state.gen_all_done = True
            st.rerun()

    conn.close()
    _mark("9_done")

    # Print timing breakdown
    labels = ["start", "1_get_project", "2_get_chapters", "3_header", "4_stepbar",
              "5_load_gen_slides", "6_load_section_plans", "7_progress_overview"]
    # Add remaining labels
    for i in range(len(labels), len(_t)):
        labels.append(f"step_{i}")
    parts = []
    for i in range(1, len(_t)):
        dt = _t[i] - _t[i-1]
        lbl = labels[i] if i < len(labels) else f"step_{i}"
        if dt > 0.005:  # only show > 5ms
            parts.append(f"{lbl}={dt*1000:.0f}ms")
    total = _t[-1] - _t[0]
    print(f"PERF render_slide_generation: total={total*1000:.0f}ms | {' | '.join(parts)}")


# ---------------------------------------------------------------------------
# Progress overview
# ---------------------------------------------------------------------------

def _render_progress_overview(chapters: list):
    gen_slides = st.session_state.gen_slides
    total_planned = 0
    total_generated = 0

    for i in range(len(chapters)):
        section_plan = st.session_state.get("section_plans", {}).get(i, {})
        total_planned += len(section_plan.get("slides", []))
        total_generated += len(gen_slides.get(i, []))

    if total_planned > 0:
        st.progress(total_generated / total_planned, text=f"Gesamt: {total_generated}/{total_planned} Folien")


# ---------------------------------------------------------------------------
# Chapter generation
# ---------------------------------------------------------------------------

def _render_chapter_generation(project, chapter, chapter_idx: int, section_plan: dict, all_chapters, conn):
    slide_plans = section_plan.get("slides", [])
    generated = st.session_state.gen_slides.get(chapter_idx, [])

    st.subheader(f"Kapitel {chapter_idx + 1}: {chapter.title}")
    st.caption(chapter.summary)

    if not slide_plans:
        st.warning("Kein Sektionsplan fuer dieses Kapitel vorhanden.")
        return

    # Controls row: text length + strategy
    prefs = load_preferences()

    text_length = st.select_slider(
        "Textumfang",
        options=TEXT_LENGTHS,
        value=st.session_state.get("gen_text_length", project.global_text_length),
        key=f"length_{chapter_idx}",
    )
    st.session_state.gen_text_length = text_length

    # Generate slides
    if len(generated) < len(slide_plans):
        _render_generation_controls(project, chapter, chapter_idx, slide_plans, generated, text_length)
    else:
        st.success(f"Alle {len(slide_plans)} Folien fuer dieses Kapitel generiert.")

    # Show generated slides (collapsed when chapter is complete to save render time)
    if generated:
        total_gen = len(generated)
        if total_gen == len(slide_plans):
            # Chapter complete — show in expander to avoid rendering 20+ cards
            with st.expander(f"Generierte Folien anzeigen ({total_gen})", expanded=False):
                for slide_data in generated:
                    render_slide_card(slide_data)
        else:
            # In progress — show last 3 slides for context
            st.subheader("Generierte Folien")
            if total_gen > 3:
                st.caption(f"{total_gen - 3} weitere Folien ausgeblendet")
            for slide_data in generated[-3:]:
                render_slide_card(slide_data)

    # Chapter review
    if len(generated) >= len(slide_plans) and slide_plans:
        st.divider()
        _render_chapter_review(project, chapter, chapter_idx, slide_plans, all_chapters, conn)


def _render_generation_controls(project, chapter, chapter_idx, slide_plans, generated, text_length):
    next_idx = len(generated)
    remaining = len(slide_plans) - next_idx

    st.info(f"Folie {next_idx + 1} von {len(slide_plans)} — {remaining} verbleibend")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Naechste Folie generieren", type="primary", use_container_width=True):
            _generate_next_slide(project, chapter, chapter_idx, slide_plans, next_idx, text_length)

    with col2:
        if st.button("Alle generieren (Batch)", use_container_width=True):
            _generate_batch(project, chapter, chapter_idx, slide_plans, next_idx, text_length)


def _generate_next_slide(project, chapter, chapter_idx, slide_plans, slide_idx, text_length):
    slide_plan = slide_plans[slide_idx]
    global_idx = _calc_global_index(chapter_idx, slide_idx)

    with st.spinner(f"Folie {slide_idx + 1} wird generiert..."):
        try:
            result = generate_slide(
                project_id=project.id,
                slide_plan=slide_plan,
                chapter_context={"title": chapter.title, "summary": chapter.summary},
                language=project.language,
                text_length=text_length,
                slide_index=slide_idx + 1,
                total_slides_in_chapter=len(slide_plans),
                project_override=project.parsed_override,
                extra_chunks=_get_pinned_chunks(chapter_idx),
            )
            _store_slide_result(chapter_idx, slide_idx, global_idx, slide_plan, result)
            st.rerun()
        except Exception as e:
            st.error(f"Fehler bei Slide-Generierung: {e}")


def _generate_batch(project, chapter, chapter_idx, slide_plans, start_idx, text_length):
    remaining_plans = slide_plans[start_idx:]
    prefs = load_preferences()
    batch_size = prefs.get("batch_size", 4)
    progress_bar = st.progress(0, text="Generiere Folien als Batch...")

    def _on_progress(done, total):
        progress_bar.progress(done / total, text=f"{done}/{total} Folien fertig...")

    try:
        results = generate_slides_batch(
            project_id=project.id,
            slide_plans=remaining_plans,
            chapter_context={"title": chapter.title, "summary": chapter.summary},
            language=project.language,
            text_length=text_length,
            project_override=project.parsed_override,
            batch_size=batch_size,
            on_progress=_on_progress,
        )

        for i, result in enumerate(results):
            slide_idx = start_idx + i
            global_idx = _calc_global_index(chapter_idx, slide_idx)
            _store_slide_result(chapter_idx, slide_idx, global_idx, slide_plans[slide_idx], result)

        st.rerun()
    except Exception as e:
        st.error(f"Fehler bei Batch-Generierung: {e}")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_pinned_chunks(chapter_idx: int) -> list[dict]:
    """Get manually pinned chunks for a chapter from section planning."""
    return st.session_state.get("pinned_chunks", {}).get(chapter_idx, [])


def _calc_global_index(chapter_idx: int, slide_idx: int) -> int:
    return sum(len(st.session_state.gen_slides.get(i, [])) for i in range(chapter_idx)) + slide_idx + 1


def _store_slide_result(chapter_idx: int, slide_idx: int, global_idx: int, slide_plan: dict, result: dict):
    result["slide_index"] = global_idx
    result["slide_index_in_chapter"] = slide_idx + 1
    result["template_type"] = slide_plan.get("template_type", "")
    result["is_reused"] = bool(slide_plan.get("reused_slide_id"))

    if chapter_idx not in st.session_state.gen_slides:
        st.session_state.gen_slides[chapter_idx] = []
    st.session_state.gen_slides[chapter_idx].append(result)

    # Persist draft to DB so it survives page navigation/refresh
    _save_gen_slides_draft(chapter_idx)


# ---------------------------------------------------------------------------
# Draft persistence — gen_slides survive page navigation and refresh
# ---------------------------------------------------------------------------

def _draft_label(chapter_idx: int) -> str:
    return f"{_GEN_DRAFT_PREFIX}{chapter_idx}"


def _save_gen_slides_draft(chapter_idx: int):
    """Persist generated slides for a chapter as a draft in the versions table."""
    project_id = st.session_state.get("current_project_id")
    if not project_id:
        return
    slides = st.session_state.gen_slides.get(chapter_idx, [])
    conn = get_connection(DB_PATH)
    save_versioned_state(conn, project_id, _draft_label(chapter_idx), chapter_idx, slides)
    conn.close()


def _load_section_plans_from_db(conn, project_id: str):
    """Load section plans from versions table (needed for progress display)."""
    st.session_state.section_plans = load_versioned_states(conn, project_id, "section_plan_")


def _load_gen_slides_from_db(conn, project_id: str):
    """Restore gen_slides drafts from the versions table."""
    st.session_state.gen_slides = load_versioned_states(conn, project_id, _GEN_DRAFT_PREFIX)


def _detect_current_chapter_idx(chapters_db) -> int:
    """Detect which chapter the user should continue generating from."""
    gen_slides = st.session_state.get("gen_slides", {})
    section_plans = st.session_state.get("section_plans", {})

    for i, ch in enumerate(chapters_db):
        if ch.status == "approved":
            continue
        plan = section_plans.get(i, {})
        planned = len(plan.get("slides", []))
        generated = len(gen_slides.get(i, []))
        if generated < planned or planned == 0:
            return i

    return len(chapters_db)  # All done


# ---------------------------------------------------------------------------
# Chapter review
# ---------------------------------------------------------------------------

def _render_chapter_review(project, chapter, chapter_idx, slide_plans, all_chapters, conn):
    st.subheader("Kapitel-Review")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Kapitel freigeben", type="primary", use_container_width=True, key=f"approve_ch_{chapter_idx}"):
            _save_chapter_slides(project, chapter, chapter_idx, conn)
            if chapter_idx + 1 < len(all_chapters):
                st.session_state.gen_chapter_idx = chapter_idx + 1
            else:
                st.session_state.gen_all_done = True
            st.rerun()

    with col2:
        if st.button("Kapitel neu generieren", use_container_width=True, key=f"regen_ch_{chapter_idx}"):
            st.session_state.gen_slides[chapter_idx] = []
            st.rerun()

    with col3:
        if st.button("Quellen hinzufuegen", use_container_width=True, key=f"sources_ch_{chapter_idx}"):
            st.session_state.current_page = "projects"
            st.rerun()

    # Single slide regeneration
    with st.expander("Einzelne Folie neu generieren"):
        generated = st.session_state.gen_slides.get(chapter_idx, [])
        slide_options = [f"Folie {s.get('slide_index_in_chapter', '?')}: {s.get('title', '?')}" for s in generated]
        if slide_options:
            selected = st.selectbox("Folie auswaehlen", range(len(slide_options)), format_func=lambda i: slide_options[i])
            if st.button("Diese Folie neu generieren", key=f"regen_single_{chapter_idx}"):
                st.session_state.gen_slides[chapter_idx] = generated[:selected]
                st.rerun()


def _save_chapter_slides(project, chapter, chapter_idx, conn):
    generated = st.session_state.gen_slides.get(chapter_idx, [])
    if not generated:
        return

    version = Version(
        project_id=project.id,
        chapter_index=chapter_idx,
        state="reviewed",
    )
    create_version(conn, version)

    for slide_data in generated:
        content_json = json.dumps(slide_data.get("content", {}), ensure_ascii=False)
        slide = Slide(
            chapter_id=chapter.id,
            project_id=project.id,
            slide_index=slide_data.get("slide_index", 0),
            slide_index_in_chapter=slide_data.get("slide_index_in_chapter", 0),
            template_type=slide_data.get("template_type", ""),
            title=slide_data.get("title", ""),
            subtitle=slide_data.get("subtitle"),
            content_json=content_json,
            speaker_notes=slide_data.get("speaker_notes", ""),
            chain_of_thought=slide_data.get("chain_of_thought", ""),
            is_reused=slide_data.get("is_reused", False),
        )
        create_slide(conn, slide)

    update_chapter_status(conn, chapter.id, "approved")


def _render_completion(project, chapters, conn):
    st.success("Alle Kapitel wurden generiert und freigegeben!")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Weiter zum Review & Export", type="primary", use_container_width=True):
            st.session_state.current_page = "review"
            st.rerun()
    with col2:
        if st.button("Zurueck zur Kapiteluebersicht", use_container_width=True):
            st.session_state.gen_chapter_idx = 0
            st.session_state.gen_all_done = False
            st.rerun()
    with col3:
        _render_txt_download(project, chapters, key="txt_dl_completion")
    with col4:
        _render_pptx_download(project, chapters, key="pptx_dl_completion")


def _render_txt_download(project, chapters, key: str = "txt_dl"):
    """Render a download button for TXT export — built lazily on first click."""
    gen_slides = st.session_state.get("gen_slides", {})
    if not gen_slides:
        return
    # Only build export when cached or after user triggers it
    if "_txt_cache" in st.session_state:
        st.download_button(
            "Als TXT herunterladen",
            data=st.session_state._txt_cache,
            file_name=f"{project.name.replace(' ', '_')}_slides.txt",
            mime="text/plain",
            use_container_width=True,
            key=key,
        )
    else:
        if st.button("TXT Export vorbereiten", use_container_width=True, key=key):
            st.session_state._txt_cache = export_gen_slides_txt(project.name, gen_slides, chapters)
            st.rerun()


def _render_pptx_download(project, chapters, key: str = "pptx_dl"):
    """Render a download button for PPTX export — built lazily on first click."""
    gen_slides = st.session_state.get("gen_slides", {})
    if not gen_slides:
        return
    if "_pptx_cache" in st.session_state and st.session_state._pptx_cache is not None:
        st.download_button(
            "Als PPTX herunterladen",
            data=st.session_state._pptx_cache,
            file_name=f"{project.name.replace(' ', '_')}_slides.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True,
            key=key,
        )
    else:
        if st.button("PPTX Export vorbereiten", use_container_width=True, key=key):
            with st.spinner("PPTX wird erstellt..."):
                try:
                    st.session_state._pptx_cache = export_pptx(project.name, gen_slides, chapters)
                except Exception as e:
                    st.error(f"PPTX-Export fehlgeschlagen: {e}")
                    return
            st.rerun()
