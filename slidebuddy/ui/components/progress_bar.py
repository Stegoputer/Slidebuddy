import streamlit as st


def render_progress(current: int, total: int, label: str = "Fortschritt"):
    """Render a progress bar with label."""
    progress = current / total if total > 0 else 0
    st.progress(progress, text=f"{label}: {current}/{total}")
