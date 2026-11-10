import sys
from pathlib import Path

# Fix import paths
ROOT_DIR = Path(__file__).resolve().parent
if ROOT_DIR.name == "app":
    ROOT_DIR = ROOT_DIR.parent
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "app"))

import streamlit as st

from ui.state import (
    AppState,
    initialize_session_state,
)
from ui.theme import apply_theme
from ui.sidebar import render_sidebar
from ui.editor import render_editor_page
from ui.broll import render_broll_page
from ui.export import render_export_page

# Path configuration
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)


def run_app():
    # Set wide layout and expanded sidebar
    st.set_page_config(
        page_title="AI Video Editor",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize FSM and session state
    initialize_session_state()

    # Apply modern dark theme with purple accents matching reference image
    apply_theme()

    # Render left sidebar (branding, navigation, and engine status)
    render_sidebar(TEMP_DIR)

    # Route main workspace based on active sidebar navigation
    active_page = st.session_state.get("current_page", "editor")

    if active_page == "editor":
        render_editor_page(TEMP_DIR)
    elif active_page == "broll":
        render_broll_page(TEMP_DIR)
    elif active_page == "export":
        render_export_page()
    else:
        render_editor_page(TEMP_DIR)


if __name__ == "__main__":
    run_app()
