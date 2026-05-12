import uuid
import streamlit as st

from pathlib import Path
from core.utils import clear_temp_directory


def initialize_session_state():

    defaults = {
        "temp_files": [],
        "uploader_key": "uploaded_video",
        "processed_video": None,
        "is_processing": False,
        "processing_complete": False
    }

    for key, value in defaults.items():

        if key not in st.session_state:
            st.session_state[key] = value


def reset_and_clear_all(temp_dir: Path):

    clear_temp_directory(temp_dir)

    st.session_state.temp_files = []
    st.session_state.processed_video = None
    st.session_state.is_processing = False
    st.session_state.processing_complete = False

    st.session_state.uploader_key = str(
        uuid.uuid4()
    )

    st.success(
        "All files cleared and reset successfully!"
    )

    st.rerun()