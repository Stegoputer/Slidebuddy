"""Workflow step bar — shows progress and allows free navigation between steps.

Navigation between steps is always allowed without data loss.
Deletion only happens when the user explicitly re-starts a previous step
(e.g. re-generating chapters when sections already exist).
"""

import streamlit as st

from slidebuddy.core.progress import (
    STEP_LABELS,
    WORKFLOW_STEPS,
    detect_project_step,
    get_page_for_step,
    get_step_index,
)


def render_stepbar(conn, project_id: str, current_step: str):
    """Render the workflow step bar at the top of each page."""
    # Cache the max step per project to avoid repeated DB queries
    cache_key = f"_stepbar_max_{project_id}"
    cached = st.session_state.get(cache_key)
    if cached is None:
        cached = detect_project_step(conn, project_id)
        st.session_state[cache_key] = cached
    max_idx = get_step_index(cached)
    current_idx = get_step_index(current_step)

    cols = st.columns(len(WORKFLOW_STEPS))
    for i, (step_name, page) in enumerate(WORKFLOW_STEPS):
        label = STEP_LABELS.get(step_name, step_name)
        with cols[i]:
            if i == current_idx:
                st.button(
                    f">> {label} <<",
                    key=f"step_{step_name}",
                    disabled=True,
                    use_container_width=True,
                )
            elif i <= max_idx:
                if st.button(label, key=f"step_{step_name}", use_container_width=True):
                    st.session_state.current_page = page
                    st.rerun()
            else:
                st.button(
                    label,
                    key=f"step_{step_name}",
                    disabled=True,
                    use_container_width=True,
                )
