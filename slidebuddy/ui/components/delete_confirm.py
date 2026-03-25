"""Reusable delete confirmation — extracted from chapter/section planning.

Two-state pattern: click delete -> show warning with confirm/cancel.
"""

import streamlit as st


def render_delete_button(
    item_name: str,
    confirm_key: str,
    widget_key: str,
    on_delete: callable,
) -> bool:
    """Render a delete button with inline confirmation.

    Args:
        item_name: Human-readable name shown in the warning.
        confirm_key: Session state key for tracking confirmation state.
        widget_key: Unique Streamlit widget key prefix.
        on_delete: Called when user confirms deletion.

    Returns:
        True if currently showing confirmation (caller should hide other content).
    """
    if st.session_state.get(confirm_key, False):
        st.warning(f"'{item_name}' wirklich loeschen?")
        c1, c2, _ = st.columns([1, 1, 4])
        with c1:
            if st.button("Ja, loeschen", key=f"{widget_key}_yes", type="primary"):
                st.session_state[confirm_key] = False
                on_delete()
                st.rerun()
        with c2:
            if st.button("Abbrechen", key=f"{widget_key}_no"):
                st.session_state[confirm_key] = False
                st.rerun()
        return True  # Confirmation active — caller should hide fields

    return False


def render_delete_trigger(confirm_key: str, widget_key: str):
    """Render the initial delete button that triggers confirmation."""
    if st.button("delete", key=widget_key):
        st.session_state[confirm_key] = True
        st.rerun()
