"""Reusable reorder component — extracted from chapter/section planning.

Provides up/down arrow reordering on a draft copy of items,
with confirm/cancel to apply or discard the new order.
"""

from typing import Callable

import streamlit as st


def render_reorder(
    items: list[dict],
    key_prefix: str,
    item_label: Callable[[dict, int], str],
    on_confirm: Callable[[list[dict]], None],
    on_cancel: Callable[[], None],
):
    """Render a reorderable list with confirm/cancel.

    Args:
        items: The list of items to reorder (operates on a draft copy).
        key_prefix: Unique prefix for Streamlit widget keys.
        item_label: Callable(item, index) -> display string for each item.
        on_confirm: Called with the reordered list when user confirms.
        on_cancel: Called when user cancels.
    """
    draft_key = f"_reorder_draft_{key_prefix}"

    if draft_key not in st.session_state:
        st.session_state[draft_key] = [item.copy() for item in items]

    draft = st.session_state[draft_key]

    st.info("Reihenfolge aendern — benutze die Pfeile zum Verschieben.")

    for i, item in enumerate(draft):
        with st.container(border=True):
            cols = st.columns([1, 1, 10], gap="small")
            with cols[0]:
                if i > 0 and st.button("up", key=f"{key_prefix}_up_{i}"):
                    draft[i], draft[i - 1] = draft[i - 1], draft[i]
                    st.session_state[draft_key] = draft
                    st.rerun()
            with cols[1]:
                if i < len(draft) - 1 and st.button("down", key=f"{key_prefix}_down_{i}"):
                    draft[i], draft[i + 1] = draft[i + 1], draft[i]
                    st.session_state[draft_key] = draft
                    st.rerun()
            with cols[2]:
                st.markdown(f"**{i + 1}.** {item_label(item, i)}")

    col_ok, col_cancel, _ = st.columns([1, 1, 4])
    with col_ok:
        if st.button("Uebernehmen", type="primary", key=f"{key_prefix}_ok", use_container_width=True):
            result = list(draft)
            st.session_state.pop(draft_key, None)
            on_confirm(result)
            st.rerun()
    with col_cancel:
        if st.button("Abbrechen", key=f"{key_prefix}_cancel", use_container_width=True):
            st.session_state.pop(draft_key, None)
            on_cancel()
            st.rerun()
