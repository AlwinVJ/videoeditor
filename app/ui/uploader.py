from pathlib import Path
import streamlit as st
import cv2
import numpy as np

from core.utils import generate_safe_filename, get_file_fingerprint
from core.video_io import get_video_metadata
from app.ui.state import AppState, set_state


def save_uploaded_file(uploaded_file, temp_dir: Path) -> Path:
    """
    Save the uploaded file idempotently.
    Avoids re-writing the file to disk on every Streamlit rerun if it hasn't changed.
    """
    fingerprint = get_file_fingerprint(uploaded_file.name, uploaded_file.size)

    # If the file is already cached and exists on disk, reuse it
    cached_path = st.session_state.get("input_video_path")
    if (
        st.session_state.get("uploaded_file_id") == fingerprint
        and cached_path
        and Path(cached_path).exists()
    ):
        return Path(cached_path)

    # New video uploaded: save file and extract metadata
    safe_name = generate_safe_filename(uploaded_file.name)
    file_path = temp_dir / safe_name

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.session_state.uploaded_file_id = fingerprint
    st.session_state.input_video_path = str(file_path)

    # Extract and store metadata
    try:
        metadata = get_video_metadata(file_path)
        st.session_state.video_metadata = metadata
    except Exception as e:
        print(f"Could not extract video metadata: {e}")
        st.session_state.video_metadata = {}

    # Reset any previous job output since a new file was uploaded
    st.session_state.processed_video = None
    st.session_state.active_job_id = None
    st.session_state.completed_job_id = None
    st.session_state.error_message = None
    set_state(AppState.UPLOADED)

    if file_path not in st.session_state.temp_files:
        st.session_state.temp_files.append(file_path)

    return file_path


def render_video_uploader():
    """Render the main video uploader widget."""
    uploaded_file = st.file_uploader(
        "Upload a video",
        type=["mp4", "mov", "avi"],
        key=st.session_state.uploader_key,
    )

    if not uploaded_file and st.session_state.get("app_state") != AppState.IDLE:
        # File was cleared by user
        st.session_state.uploaded_file_id = None
        st.session_state.input_video_path = None
        st.session_state.processed_video = None
        st.session_state.video_metadata = {}
        st.session_state.active_job_id = None
        st.session_state.completed_job_id = None
        set_state(AppState.IDLE)

    return uploaded_file


def render_background_uploader():
    """Render the background image uploader for replacement effect."""
    uploaded_bg = st.file_uploader(
        "Upload Background Image",
        type=["jpg", "png", "jpeg"],
        key="bg_image_uploader",
    )

    bg_image = None
    if uploaded_bg:
        file_bytes = np.asarray(bytearray(uploaded_bg.read()), dtype=np.uint8)
        bg_image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    return uploaded_bg, bg_image
