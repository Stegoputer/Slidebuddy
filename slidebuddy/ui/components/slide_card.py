import json

import streamlit as st


def render_slide_card(
    slide: dict,
    show_cot: bool = True,
    edit_key: str | None = None,
    on_save=None,
):
    """Render a single slide as a card.

    edit_key: if provided, shows an edit toggle button. Requires on_save callback.
    on_save: callable(updated_slide) — called when user saves edits.
    """
    template_label = slide.get("template_type", "").replace("_", " ").title()
    reuse_marker = " ♻️" if slide.get("is_reused") else ""
    is_editing = edit_key and st.session_state.get(f"_edit_open_{edit_key}", False)

    with st.container(border=True):
        if edit_key:
            header_col, btn_col = st.columns([8, 1])
            with header_col:
                st.markdown(
                    f"**Slide {slide.get('slide_index', '?')}: {slide.get('title', 'Ohne Titel')}**"
                    f" — {template_label}{reuse_marker}"
                )
            with btn_col:
                label = "✕" if is_editing else "✏️"
                if st.button(label, key=f"_edit_toggle_{edit_key}"):
                    st.session_state[f"_edit_open_{edit_key}"] = not is_editing
                    st.rerun()
        else:
            st.markdown(
                f"**Slide {slide.get('slide_index', '?')}: {slide.get('title', 'Ohne Titel')}**"
                f" — {template_label}{reuse_marker}"
            )

        if is_editing:
            _render_slide_edit(slide, edit_key, on_save)
        else:
            _render_slide_display(slide, show_cot)


def _render_slide_display(slide: dict, show_cot: bool):
    if slide.get("subtitle"):
        st.caption(slide["subtitle"])

    raw_content = slide.get("content") or slide.get("content_json")
    if raw_content:
        try:
            content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
            if isinstance(content, dict):
                _render_content(content, slide.get("template_type", ""))
            else:
                st.text(str(content))
        except (json.JSONDecodeError, TypeError):
            st.text(str(raw_content))

    if slide.get("speaker_notes"):
        with st.expander("Sprechernotizen"):
            st.markdown(slide["speaker_notes"])

    if show_cot and slide.get("chain_of_thought"):
        with st.expander("Chain of Thought"):
            st.markdown(slide["chain_of_thought"])


def _render_slide_edit(slide: dict, edit_key: str, on_save):
    """Inline edit form for a slide."""
    new_title = st.text_input("Titel", value=slide.get("title", ""), key=f"_e_title_{edit_key}")
    new_subtitle = st.text_input("Untertitel", value=slide.get("subtitle") or "", key=f"_e_sub_{edit_key}")

    raw = slide.get("content") or slide.get("content_json") or {}
    content_str = json.dumps(raw, ensure_ascii=False, indent=2) if isinstance(raw, dict) else (raw or "{}")
    new_content_str = st.text_area(
        "Inhalt (JSON)", value=content_str, height=220, key=f"_e_content_{edit_key}"
    )

    new_notes = st.text_area(
        "Sprechernotizen", value=slide.get("speaker_notes", ""), height=100, key=f"_e_notes_{edit_key}"
    )

    if st.button("💾 Speichern", key=f"_e_save_{edit_key}", type="primary"):
        try:
            new_content = json.loads(new_content_str)
        except json.JSONDecodeError:
            st.error("Ungültiges JSON im Inhalt — bitte korrigieren.")
            return

        updated = {
            **slide,
            "title": new_title,
            "subtitle": new_subtitle or None,
            "content": new_content,
            "speaker_notes": new_notes,
        }
        updated.pop("content_json", None)

        if on_save:
            on_save(updated)
        st.session_state[f"_edit_open_{edit_key}"] = False
        st.rerun()


def _render_content(content: dict, template_type: str):
    """Render content based on template type."""
    if template_type == "two_column":
        col1, col2 = st.columns(2)
        with col1:
            if content.get("left_box"):
                st.markdown(f"**{content['left_box'].get('heading', '')}**")
                st.markdown(content["left_box"].get("text", ""))
        with col2:
            if content.get("right_box"):
                st.markdown(f"**{content['right_box'].get('heading', '')}**")
                st.markdown(content["right_box"].get("text", ""))
        if content.get("conclusion"):
            st.info(content["conclusion"])

    elif template_type == "numbered":
        for point in content.get("points", []):
            st.markdown(f"**{point.get('number', '')}. {point.get('heading', '')}**")
            st.markdown(f"   {point.get('text', '')}")

    elif template_type == "three_horizontal":
        cols = st.columns(3)
        for i, col_data in enumerate(content.get("columns", [])):
            with cols[i]:
                st.markdown(f"**{col_data.get('heading', '')}**")
                st.markdown(col_data.get("text", ""))

    elif template_type == "grid":
        boxes = content.get("boxes", [])
        if len(boxes) >= 2:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{boxes[0].get('heading', '')}**")
                st.markdown(boxes[0].get("text", ""))
            with col2:
                st.markdown(f"**{boxes[1].get('heading', '')}**")
                st.markdown(boxes[1].get("text", ""))
        if len(boxes) >= 4:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{boxes[2].get('heading', '')}**")
                st.markdown(boxes[2].get("text", ""))
            with col2:
                st.markdown(f"**{boxes[3].get('heading', '')}**")
                st.markdown(boxes[3].get("text", ""))

    elif template_type == "detail":
        for section in content.get("sections", []):
            st.markdown(f"### {section.get('heading', '')}")
            for bullet in section.get("bullets", []):
                st.markdown(f"- **{bullet.get('heading', '')}**: {bullet.get('text', '')}")

    elif template_type == "quote":
        st.markdown(f"> *{content.get('text', '')}*")

    else:
        _render_generic_content(content)


def _render_generic_content(content: dict):
    """Render content generically — works for any template structure."""
    for key, value in content.items():
        if isinstance(value, str) and value.strip():
            label = key.replace("_", " ").replace("placeholder", "").strip().title()
            st.markdown(f"**{label}:** {value}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    parts = [
                        f"**{k}**: {v}"
                        for k, v in item.items()
                        if isinstance(v, str) and v.strip()
                    ]
                    if parts:
                        st.markdown(" | ".join(parts))
                elif isinstance(item, str):
                    st.markdown(f"- {item}")
        elif isinstance(value, dict):
            label = key.replace("_", " ").title()
            st.markdown(f"**{label}:**")
            for k, v in value.items():
                if isinstance(v, str) and v.strip():
                    st.markdown(f"  - {k}: {v}")
