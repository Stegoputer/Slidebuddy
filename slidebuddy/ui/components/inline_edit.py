"""Reusable inline edit components for Streamlit.

Fields are always editable — no lock/unlock flow.
Changes auto-save via on_change callback when the user leaves the field.
"""

from typing import Any, Callable, Optional

import streamlit as st


def inline_text(
    label: str,
    value: str,
    key: str,
    multiline: bool = False,
    on_change: Optional[Callable] = None,
) -> str:
    """Always-editable text field with auto-save."""
    input_key = f"input_{key}"

    # Initialise widget value on first render
    if input_key not in st.session_state:
        st.session_state[input_key] = value

    def _on_change():
        new_val = st.session_state[input_key]
        if on_change:
            on_change(new_val)

    if multiline:
        st.text_area(label, key=input_key, on_change=_on_change)
    else:
        st.text_input(label, key=input_key, on_change=_on_change)

    return st.session_state[input_key]


def inline_number(
    label: str,
    value: int,
    key: str,
    min_value: int = 1,
    max_value: int = 50,
    on_change: Optional[Callable] = None,
) -> int:
    """Always-editable number field with auto-save."""
    input_key = f"input_{key}"

    if input_key not in st.session_state:
        st.session_state[input_key] = value

    def _on_change():
        new_val = int(st.session_state[input_key])
        if on_change:
            on_change(new_val)

    st.number_input(
        label, min_value=min_value, max_value=max_value,
        key=input_key, on_change=_on_change,
    )

    return int(st.session_state[input_key])


def inline_select(
    label: str,
    value: str,
    options: list[str],
    key: str,
    on_change: Optional[Callable] = None,
) -> str:
    """Always-editable select/dropdown with auto-save."""
    input_key = f"input_{key}"

    if input_key not in st.session_state:
        current_idx = options.index(value) if value in options else 0
        st.session_state[input_key] = options[current_idx]

    def _on_change():
        new_val = st.session_state[input_key]
        if on_change:
            on_change(new_val)

    st.selectbox(label, options, key=input_key, on_change=_on_change)

    return st.session_state[input_key]
