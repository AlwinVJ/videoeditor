import sys
from pathlib import Path
import uuid

# Fix import path
ROOT_DIR = Path(__file__).resolve().parent
if ROOT_DIR.name == "app":
    ROOT_DIR = ROOT_DIR.parent
sys.path.append(str(ROOT_DIR))

import streamlit as st
import numpy as np
import cv2

from core.utils import generate_safe_filename, clear_temp_directory
from core.video_io import process_video

from ui.state import initialize_session_state, reset_and_clear_all

from ui.uploader import (
    save_uploaded_file,
    render_video_uploader,
    render_background_uploader,
)

from ui.controls import render_effect_controls
from ui.preview import (
    show_video_comparison,
    show_background_preview,
    show_download_button,
    show_uploaded_video_preview,
)

# Path configuration
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Video Background Editor", layout="wide")

# Handling session state
initialize_session_state()

effect = "none"
uploaded_bg = None
bg_image = None


# UI
st.title("🎬 Video Background Editor")

if st.button("Reset and Clear All"):
    reset_and_clear_all(TEMP_DIR)

uploaded_file = render_video_uploader()

if uploaded_file:

    # File path saved
    file_path = save_uploaded_file(uploaded_file, TEMP_DIR)
    # Preview original
    st.subheader("Preview")
    col1, col2, col3 = st.columns([3, 0.5, 2])
    show_uploaded_video_preview(uploaded_file, file_path, col1)

    # Save file

    if file_path not in st.session_state.temp_files:
        st.session_state.temp_files.append(file_path)

    # Effects
    effect, blur_strength, bg_image, uploaded_bg = render_effect_controls(col3)

    # Background preview
    show_background_preview(bg_image, uploaded_bg, col3)

    def start_processing():
        st.session_state.is_processing = True

    process_btn = st.button(
        "Process Video",
        on_click=start_processing,
        disabled=st.session_state.is_processing,
    )

    if st.session_state.get("processing_complete"):
        st.success("Processing complete!")
        st.session_state.processing_complete = False

    if st.session_state.is_processing:
        output_path = TEMP_DIR / f"processed_{file_path.stem}.mp4"

        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("Processing video... 0%")

        def update_progress(progress):
            progress_bar.progress(progress)
            status_text.text(f"Processing video... {int(progress * 100)}%")

        try:
            with st.spinner("Making changes ..."):
                process_video(
                    file_path,
                    output_path,
                    effect,
                    bg_image,
                    blur_strength,
                    progress_callback=update_progress,
                )

            progress_bar.empty()
            status_text.empty()
            st.session_state.processing_complete = True

            # Save to session
            st.session_state.processed_video = str(output_path)

            if output_path not in st.session_state.temp_files:
                st.session_state.temp_files.append(output_path)

        finally:
            st.session_state.is_processing = False
            st.rerun()

    if st.session_state.processed_video:
        st.divider()
        st.subheader("Result")

        col1, col2 = st.columns(2)

        video_path = Path(st.session_state.processed_video)

        show_video_comparison(uploaded_file, video_path, col1, col2)

        # Download
        with open(video_path, "rb") as f:
            st.download_button(
                label="Download Processed Video",
                data=f,
                file_name="processed_video.mp4",
                mime="video/mp4",
            )
