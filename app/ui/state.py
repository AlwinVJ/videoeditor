import uuid
from pathlib import Path
import streamlit as st

from core.utils import clear_temp_directory


class AppState:
    IDLE = "IDLE"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PREVIEW = "PREVIEW"
    EXPORTED = "EXPORTED"
    FAILED = "FAILED"


def initialize_session_state():
    """Initialize all session state variables with explicit defaults."""
    defaults = {
        "app_state": AppState.IDLE,
        "active_job_id": None,
        "completed_job_id": None,
        "uploaded_file_id": None,
        "input_video_path": None,
        "processed_video": None,
        "video_metadata": {},
        "processing_progress": 0.0,
        "processing_status_text": "Ready",
        "error_message": None,
        "temp_files": [],
        "uploader_key": "uploader_init",
        # Retain backward compatibility flags
        "is_processing": False,
        "processing_complete": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_state(new_state: str):
    """Transition to a new application state with synchronized legacy flags."""
    st.session_state.app_state = new_state
    st.session_state.is_processing = (new_state == AppState.PROCESSING)
    st.session_state.processing_complete = (
        new_state in (AppState.COMPLETED, AppState.PREVIEW, AppState.EXPORTED)
    )


def reset_and_clear_all(temp_dir: Path):
    """Wipe temporary directory and reset entire application state."""
    clear_temp_directory(temp_dir)

    st.session_state.app_state = AppState.IDLE
    st.session_state.active_job_id = None
    st.session_state.completed_job_id = None
    st.session_state.uploaded_file_id = None
    st.session_state.input_video_path = None
    st.session_state.processed_video = None
    st.session_state.video_metadata = {}
    st.session_state.processing_progress = 0.0
    st.session_state.processing_status_text = "Ready"
    st.session_state.error_message = None
    st.session_state.temp_files = []
    st.session_state.is_processing = False
    st.session_state.processing_complete = False

    # Force a fresh file uploader widget key
    st.session_state.uploader_key = str(uuid.uuid4())

    st.success("All files cleared and reset successfully!")
    st.rerun()
