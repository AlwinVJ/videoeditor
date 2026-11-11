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

    # Explicit allowed transitions
    VALID_TRANSITIONS = {
        IDLE: {UPLOADED, IDLE},
        UPLOADED: {PROCESSING, IDLE, UPLOADED},
        PROCESSING: {COMPLETED, FAILED},
        COMPLETED: {PREVIEW, EXPORTED, PROCESSING, IDLE, UPLOADED},
        PREVIEW: {EXPORTED, PROCESSING, IDLE, UPLOADED},
        EXPORTED: {PREVIEW, PROCESSING, IDLE, UPLOADED},
        FAILED: {PROCESSING, IDLE, UPLOADED},
    }


def initialize_session_state():
    """Initialize all session state variables with explicit defaults."""
    defaults = {
        "current_page": "editor",  # "editor" | "broll" | "export"
        "preview_mode": "comparison",  # "comparison" | "processed_only"
        "app_state": AppState.IDLE,
        "active_job_id": None,
        "completed_job_id": None,
        "uploaded_file_id": None,
        "uploaded_file_name": None,
        "uploaded_file_size": 0,
        "input_video_path": None,
        "processed_video": None,
        "video_metadata": {},
        "processing_progress": 0.0,
        "processing_status_text": "Ready",
        "error_message": None,
        "temp_files": [],
        "uploader_key": "uploader_init",
        # Backward compatibility flags
        "is_processing": False,
        "processing_complete": False,
        # Edit settings state
        "selected_effect": "Replace Background",
        "blur_option": "Medium",
        "bg_image_name": None,
        "bg_image_size": 0,
        # B-roll session state
        "broll_input_video": None,
        "broll_source": None,  # "transferred" | "uploaded"
        "broll_preview_active": False,
        "broll_uploader_key": "broll_uploader_init",
        "broll_transcript": None,
        "broll_transcript_video_id": None,
        "broll_transcription_error": None,
        "broll_keywords": None,
        "broll_keywords_video_id": None,
        "broll_keywords_error": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_state(new_state: str):
    """
    Transition to a new application state with validation and
    synchronized legacy flags.
    """
    current_state = st.session_state.get("app_state", AppState.IDLE)
    allowed = AppState.VALID_TRANSITIONS.get(current_state, set())

    if new_state not in allowed and new_state != current_state:
        print(f"Warning: Unexpected state transition from {current_state} to {new_state}")

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
    st.session_state.uploaded_file_name = None
    st.session_state.uploaded_file_size = 0
    st.session_state.input_video_path = None
    st.session_state.processed_video = None
    st.session_state.video_metadata = {}
    st.session_state.processing_progress = 0.0
    st.session_state.processing_status_text = "Ready"
    st.session_state.error_message = None
    st.session_state.temp_files = []
    st.session_state.is_processing = False
    st.session_state.processing_complete = False
    st.session_state.preview_mode = "comparison"
    st.session_state.bg_image_name = None
    st.session_state.bg_image_size = 0
    st.session_state.broll_input_video = None
    st.session_state.broll_source = None
    st.session_state.broll_preview_active = False
    st.session_state.broll_uploader_key = str(uuid.uuid4())[:8]
    st.session_state.broll_transcript = None
    st.session_state.broll_transcript_video_id = None
    st.session_state.broll_transcription_error = None
    st.session_state.broll_keywords = None
    st.session_state.broll_keywords_video_id = None
    st.session_state.broll_keywords_error = None

    # Force a fresh file uploader widget key
    st.session_state.uploader_key = str(uuid.uuid4())

    st.success("All files cleared and reset successfully!")
    st.rerun()
