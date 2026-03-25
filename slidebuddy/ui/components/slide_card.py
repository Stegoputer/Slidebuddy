import streamlit as st
import json


def render_slide_card(slide: dict, show_cot: bool = True):
    """Render a single slide as a card."""
    template_label = slide.get("template_type", "").replace("_", " ").title()
    reuse_marker = " ♻️" if slide.get("is_reused") else ""

    with st.container(border=True):
        st.markdown(f"**Slide {slide.get('slide_index', '?')}: {slide.get('title', 'Ohne Titel')}** — {template_label}{reuse_marker}")

        if slide.get("subtitle"):
            st.caption(slide["subtitle"])

        # Content — handle both "content" (from generation) and "content_json" (from DB)
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

        # Speaker notes
        if slide.get("speaker_notes"):
            with st.expander("Sprechernotizen"):
                st.markdown(slide["speaker_notes"])

        # Chain of thought
        if show_cot and slide.get("chain_of_thought"):
            with st.expander("Chain of Thought"):
                st.markdown(slide["chain_of_thought"])


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
        # Dynamic fallback for master templates and unknown types
        _render_generic_content(content)


def _render_generic_content(content: dict):
    """Render content generically — works for any template structure."""
    for key, value in content.items():
        if isinstance(value, str) and value.strip():
            # Simple text field
            label = key.replace("_", " ").replace("placeholder", "").strip().title()
            st.markdown(f"**{label}:** {value}")
        elif isinstance(value, list):
            # List of items
            for item in value:
                if isinstance(item, dict):
                    parts = []
                    for k, v in item.items():
                        if isinstance(v, str) and v.strip():
                            parts.append(f"**{k}**: {v}")
                    if parts:
                        st.markdown(" | ".join(parts))
                elif isinstance(item, str):
                    st.markdown(f"- {item}")
        elif isinstance(value, dict):
            # Nested dict
            label = key.replace("_", " ").title()
            st.markdown(f"**{label}:**")
            for k, v in value.items():
                if isinstance(v, str) and v.strip():
                    st.markdown(f"  - {k}: {v}")
