import streamlit as st
from typing import Callable, Optional


def render_quick_accept(
    on_accept: Callable,
    on_iterate: Callable,
    accept_label: str = "✅ Freigeben",
    iterate_label: str = "🔄 Ändern",
    feedback_placeholder: str = "Was soll geändert werden?",
):
    """Render quick accept / iterate buttons with optional feedback."""
    col1, col2 = st.columns(2)

    with col1:
        if st.button(accept_label, type="primary", use_container_width=True):
            on_accept()

    with col2:
        if st.button(iterate_label, use_container_width=True):
            st.session_state["_show_feedback"] = True

    if st.session_state.get("_show_feedback"):
        feedback = st.text_area(feedback_placeholder)
        if st.button("Feedback senden") and feedback:
            st.session_state["_show_feedback"] = False
            on_iterate(feedback)
