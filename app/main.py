import sys
from pathlib import Path
import uuid

# Fix import path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import streamlit as st
import numpy as np
import cv2

from core.utils import generate_safe_filename, clear_temp_directory
from core.video_io import process_video

# Path configuration
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Video Background Editor", layout="wide")

# Handling session state

if "temp_files" not in st.session_state:
    st.session_state.temp_files = []

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = "uploaded_video"

if "processed_video" not in st.session_state:
    st.session_state.processed_video = None

if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False


def save_uploaded_file(uploaded_file):
    safe_name = generate_safe_filename(uploaded_file.name)
    file_path = TEMP_DIR / safe_name

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return file_path


def reset_and_clear_all():
    clear_temp_directory(TEMP_DIR)

    st.session_state.temp_files = []
    st.session_state.processed_video = None

    # reset uploader
    st.session_state.uploader_key = str(uuid.uuid4())

    st.success("All files cleared and reset successfully!")
    st.rerun()


# UI
st.title("🎬 Video Background Editor")

if st.button("Reset and Clear All"):
    reset_and_clear_all()

uploaded_file = st.file_uploader(
    "Upload a video",
    type=["mp4", "mov", "avi"],
    key=st.session_state.uploader_key
)

if uploaded_file:

    # Preview original
    st.subheader("Preview")
    col1, col2, col3 = st.columns([3, 0.5, 2])
    with col1:
        st.video(uploaded_file, width=800)

    # Save file
    file_path = save_uploaded_file(uploaded_file)

    if file_path not in st.session_state.temp_files:
        st.session_state.temp_files.append(file_path)

    with col3:
        st.success(f"File saved: {file_path.name}")

    # Effects
    effect_label = st.selectbox(
        "Select Effect",
        ["None", "Blur Background", "White Background", "Replace Background"]
    )

    effect_map = {
        "None": "none",
        "Blur Background": "blur",
        "White Background": "white",
        "Replace Background": "replace"
    }

    effect = effect_map[effect_label]
    bg_image = None
    uploaded_bg = None

    if effect == "replace":
        uploaded_bg = st.file_uploader(
            "Upload Background Image",
            type=["jpg", "png"]
        )

        if uploaded_bg:
            file_bytes = np.asarray(bytearray(uploaded_bg.read()), dtype=np.uint8)
            bg_image = cv2.imdecode(file_bytes, 1)

    def start_processing():
        st.session_state.is_processing = True

    process_btn = st.button("Process Video", on_click=start_processing, disabled=st.session_state.is_processing)

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
                process_video(file_path, output_path, effect, bg_image, progress_callback=update_progress)

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
        
        with col1:
            st.subheader("Original Video")
            st.video(uploaded_file)

        with col2:
            st.subheader("Processed Video")
            st.video(str(video_path))

        # Download
        with open(video_path, "rb") as f:
            st.download_button(
                label="Download Processed Video",
                data=f,
                file_name="processed_video.mp4",
                mime="video/mp4",
            )