import streamlit as st


def render_cot_expander(chain_of_thought: str, label: str = "Chain of Thought anzeigen"):
    """Render an expandable Chain of Thought section."""
    if chain_of_thought:
        with st.expander(f"▸ {label}"):
            st.markdown(chain_of_thought)
