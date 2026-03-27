import logging
import streamlit as st
from pathlib import Path
from slidebuddy.config.defaults import DB_PATH, DATA_DIR
from slidebuddy.db.migrations import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)


@st.cache_resource
def _init_once():
    """Initialize DB only once per Streamlit server lifetime."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    init_db(DB_PATH)

_init_once()

st.set_page_config(
    page_title="SlideBuddy",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark Fintech Theme
from slidebuddy.ui.theme import inject_theme
inject_theme()

# Session state defaults
if "current_project_id" not in st.session_state:
    st.session_state.current_project_id = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "projects"

# Sidebar
from slidebuddy.ui.sidebar import render_sidebar
render_sidebar()

# Main content — route to correct page
page = st.session_state.current_page

if page == "projects":
    from slidebuddy.ui.pages.project_setup import render_project_setup
    render_project_setup()
elif page == "chapter_planning":
    from slidebuddy.ui.pages.chapter_planning import render_chapter_planning
    render_chapter_planning()
elif page == "section_planning":
    from slidebuddy.ui.pages.section_planning import render_section_planning
    render_section_planning()
elif page == "slide_generation":
    from slidebuddy.ui.pages.slide_generation import render_slide_generation
    render_slide_generation()
elif page == "review":
    from slidebuddy.ui.pages.review import render_review
    render_review()
elif page == "settings":
    from slidebuddy.ui.pages.settings import render_settings
    render_settings()
elif page == "chunk_debug":
    from slidebuddy.ui.pages.chunk_debug import render_chunk_debug
    render_chunk_debug()
elif page == "slide_masters":
    from slidebuddy.ui.pages.slide_masters import render_slide_masters
    render_slide_masters()
else:
    st.error(f"Unknown page: {page}")
