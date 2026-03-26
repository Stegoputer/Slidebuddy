"""Workflow step bar — modern dark theme with gradient active step."""

import streamlit as st
import streamlit.components.v1 as components

from slidebuddy.core.progress import (
    STEP_LABELS,
    WORKFLOW_STEPS,
    detect_project_step,
    get_page_for_step,
    get_step_index,
)

_STEPBAR_CSS = """
.sb-stepbar {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px 0;
    gap: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: transparent;
}
.sb-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    min-width: 80px;
}
.sb-circle {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 14px;
    transition: all 0.3s ease;
}
.sb-label {
    font-size: 11px;
    font-weight: 500;
    text-align: center;
    max-width: 90px;
    line-height: 1.2;
}
.sb-line {
    flex: 1;
    height: 2px;
    background: #2A2A3D;
    min-width: 30px;
    margin-bottom: 22px;
    border-radius: 1px;
}
.sb-line-done {
    flex: 1;
    height: 2px;
    background: linear-gradient(90deg, #10B981, #6C5CE7);
    min-width: 30px;
    margin-bottom: 22px;
    border-radius: 1px;
}
.sb-active .sb-circle {
    background: linear-gradient(135deg, #6C5CE7, #a855f7);
    color: white;
    box-shadow: 0 0 16px rgba(108, 92, 231, 0.5);
}
.sb-active .sb-label {
    color: #E8E8F0;
    font-weight: 600;
}
.sb-done .sb-circle {
    background: #10B981;
    color: white;
}
.sb-done .sb-label {
    color: #8B8B9E;
}
.sb-available .sb-circle {
    background: #1E1E30;
    border: 2px solid #6C5CE7;
    color: #6C5CE7;
}
.sb-available .sb-label {
    color: #8B8B9E;
}
.sb-locked .sb-circle {
    background: #1E1E30;
    border: 2px solid #2A2A3D;
    color: #5A5A72;
}
.sb-locked .sb-label {
    color: #5A5A72;
}
"""


def render_stepbar(conn, project_id: str, current_step: str):
    """Render the workflow step bar at the top of each page."""
    cache_key = f"_stepbar_max_{project_id}"
    cached = st.session_state.get(cache_key)
    if cached is None:
        cached = detect_project_step(conn, project_id)
        st.session_state[cache_key] = cached
    max_idx = get_step_index(cached)
    current_idx = get_step_index(current_step)

    total = len(WORKFLOW_STEPS)

    # Build HTML steps
    parts = []
    for i, (step_name, page) in enumerate(WORKFLOW_STEPS):
        label = STEP_LABELS.get(step_name, step_name)
        step_num = i + 1

        if i == current_idx:
            cls = "sb-step sb-active"
            icon = "&#9679;"  # ●
        elif i < current_idx and i <= max_idx:
            cls = "sb-step sb-done"
            icon = "&#10003;"  # ✓
        elif i <= max_idx:
            cls = "sb-step sb-available"
            icon = str(step_num)
        else:
            cls = "sb-step sb-locked"
            icon = str(step_num)

        parts.append(
            f'<div class="{cls}">'
            f'<div class="sb-circle">{icon}</div>'
            f'<div class="sb-label">{label}</div>'
            f"</div>"
        )
        if i < total - 1:
            line_cls = "sb-line-done" if (i < current_idx and i < max_idx) else "sb-line"
            parts.append(f'<div class="{line_cls}"></div>')

    steps_html = "\n".join(parts)

    components.html(
        f"<style>{_STEPBAR_CSS}</style>"
        f'<div class="sb-stepbar">{steps_html}</div>',
        height=80,
    )

    # Clickable navigation via small buttons below
    cols = st.columns(total)
    for i, (step_name, page) in enumerate(WORKFLOW_STEPS):
        with cols[i]:
            if i != current_idx and i <= max_idx:
                if st.button(
                    STEP_LABELS.get(step_name, step_name),
                    key=f"step_{step_name}",
                    use_container_width=True,
                    type="secondary",
                ):
                    st.session_state.current_page = page
                    st.rerun()
            else:
                st.button(
                    STEP_LABELS.get(step_name, step_name),
                    key=f"step_{step_name}",
                    disabled=True,
                    use_container_width=True,
                    type="secondary",
                )
