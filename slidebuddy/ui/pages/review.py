"""Phase 4: Review & Export — view all generated slides and export as TXT."""

import streamlit as st

from slidebuddy.config.defaults import DB_PATH
from slidebuddy.db.migrations import get_connection
from slidebuddy.db.queries import (
    get_chapters_for_project,
    get_project,
    get_slides_for_project,
)
from slidebuddy.export.txt_exporter import export_gen_slides_txt, export_txt
from slidebuddy.ui.components.slide_card import render_slide_card
from slidebuddy.ui.components.stepbar import render_stepbar


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
    slides_db = get_slides_for_project(conn, project_id)

    # Also check gen_slides drafts (not yet approved)
    gen_slides = st.session_state.get("gen_slides", {})

    if not slides_db and not any(gen_slides.values()):
        st.info("Noch keine Folien generiert.")
        conn.close()
        return

    # Export buttons
    st.subheader("Export")
    col1, col2 = st.columns(2)
    with col1:
        if slides_db:
            txt = export_txt(project.name, chapters, slides_db)
            st.download_button(
                "Freigegebene Folien als TXT",
                data=txt,
                file_name=f"{project.name.replace(' ', '_')}_final.txt",
                mime="text/plain",
                use_container_width=True,
            )
    with col2:
        if any(gen_slides.values()):
            txt = export_gen_slides_txt(project.name, gen_slides, chapters)
            st.download_button(
                "Entwuerfe als TXT",
                data=txt,
                file_name=f"{project.name.replace(' ', '_')}_draft.txt",
                mime="text/plain",
                use_container_width=True,
            )

    st.divider()

    # Show all slides grouped by chapter
    if slides_db:
        st.subheader("Freigegebene Folien")
        for chapter in chapters:
            ch_slides = [s for s in slides_db if s.chapter_id == chapter.id]
            if ch_slides:
                with st.expander(f"Kapitel {chapter.chapter_index + 1}: {chapter.title} ({len(ch_slides)} Folien)", expanded=True):
                    for slide in ch_slides:
                        render_slide_card({
                            "slide_index": slide.slide_index,
                            "title": slide.title,
                            "subtitle": slide.subtitle,
                            "template_type": slide.template_type,
                            "content_json": slide.content_json,
                            "speaker_notes": slide.speaker_notes,
                            "chain_of_thought": slide.chain_of_thought,
                            "is_reused": slide.is_reused,
                        }, show_cot=False)

    conn.close()
