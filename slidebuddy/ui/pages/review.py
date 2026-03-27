"""Phase 4: Review & Export — view all generated slides and export as TXT or PPTX."""

import streamlit as st

from slidebuddy.config.defaults import DB_PATH
from slidebuddy.db.migrations import get_connection
from slidebuddy.db.queries import get_chapters_for_project, get_project
from slidebuddy.db.helpers import load_versioned_states
from slidebuddy.export.pptx_exporter import export_pptx
from slidebuddy.export.txt_exporter import export_gen_slides_txt
from slidebuddy.ui.components.slide_card import render_slide_card
from slidebuddy.ui.components.stepbar import render_stepbar

_GEN_DRAFT_PREFIX = "gen_slides_"


def render_review():
    project_id = st.session_state.get("current_project_id")
    if not project_id:
        st.warning("Kein Projekt ausgewaehlt.")
        return

    conn = get_connection(DB_PATH)
    project = get_project(conn, project_id)
    if not project:
        st.error("Projekt nicht gefunden.")
        conn.close()
        return

    st.header(f"Review & Export — {project.name}")
    render_stepbar(conn, project_id, "generation")

    chapters = get_chapters_for_project(conn, project_id)

    # Load gen_slides from session state or DB
    if "gen_slides" not in st.session_state or not st.session_state.gen_slides:
        st.session_state.gen_slides = load_versioned_states(conn, project_id, _GEN_DRAFT_PREFIX)
    conn.close()

    gen_slides = st.session_state.get("gen_slides", {})
    if not any(gen_slides.values()):
        st.info("Noch keine Folien generiert.")
        return

    # Export buttons
    st.subheader("Export")
    col1, col2 = st.columns(2)
    with col1:
        txt = export_gen_slides_txt(project.name, gen_slides, chapters)
        st.download_button(
            "📄 Als TXT herunterladen",
            data=txt,
            file_name=f"{project.name.replace(' ', '_')}_slides.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col2:
        _render_pptx_download(project, chapters)

    st.divider()

    # Show all slides grouped by chapter, editable
    st.subheader("Folien")
    for i, chapter in enumerate(chapters):
        slides = gen_slides.get(i, [])
        if not slides:
            continue
        with st.expander(
            f"Kapitel {i + 1}: {chapter.title} ({len(slides)} Folien)", expanded=True
        ):
            for j, slide_data in enumerate(slides):
                def _on_save(updated, _i=i, _j=j):
                    st.session_state.gen_slides[_i][_j] = updated
                    _save_gen_slides_draft(_i, project.id)

                render_slide_card(
                    slide_data,
                    show_cot=False,
                    edit_key=f"review_{i}_{j}",
                    on_save=_on_save,
                )


def _render_pptx_download(project, chapters):
    """Lazily build and offer PPTX download."""
    gen_slides = st.session_state.get("gen_slides", {})
    if not any(gen_slides.values()):
        return

    if st.session_state.get("_pptx_cache_review"):
        st.download_button(
            "📊 Als PPTX herunterladen",
            data=st.session_state._pptx_cache_review,
            file_name=f"{project.name.replace(' ', '_')}_slides.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True,
            key="pptx_dl_review",
        )
    else:
        if st.button("📊 PPTX Export vorbereiten", use_container_width=True, key="pptx_prepare_review"):
            with st.spinner("PPTX wird erstellt..."):
                try:
                    st.session_state._pptx_cache_review = export_pptx(project.name, gen_slides, chapters)
                except Exception as e:
                    st.error(f"PPTX-Export fehlgeschlagen: {e}")
                    return
            st.rerun()


def _save_gen_slides_draft(chapter_idx: int, project_id: str):
    """Persist edited slides back to the versions table."""
    from slidebuddy.db.helpers import save_versioned_state
    slides = st.session_state.gen_slides.get(chapter_idx, [])
    conn = get_connection(DB_PATH)
    save_versioned_state(conn, project_id, f"{_GEN_DRAFT_PREFIX}{chapter_idx}", chapter_idx, slides)
    conn.close()
