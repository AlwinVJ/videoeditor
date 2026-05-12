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

from ui.state import (
    initialize_session_state,
    reset_and_clear_all
)

from ui.uploader import (
    save_uploaded_file,
    render_video_uploader,
    render_background_uploader
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
    file_path = save_uploaded_file(uploaded_file,TEMP_DIR) 
    # Preview original
    st.subheader("Preview")
    col1, col2, col3 = st.columns([3, 0.5, 2])
    with col1:
        st.markdown("Uploaded Video")
        st.video(uploaded_file, width=800)
        st.success(f"File saved: {file_path.name}")

    # Save file
    

    if file_path not in st.session_state.temp_files:
        st.session_state.temp_files.append(file_path)
        

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
    blur_strength = 51
    bg_image = None
    uploaded_bg = None
    
    if effect == "blur":
        blur_option = st.selectbox(
            "Blur Strength",
            ["Light", "Medium", "Strong"]
        )
    
        blur_map = {
            "Light": 21,
            "Medium": 51,
            "Strong": 101
        }
    
        blur_strength = blur_map[blur_option]

    if effect == "replace":
        uploaded_bg = render_background_uploader()

        if uploaded_bg:
            file_bytes = np.asarray(bytearray(uploaded_bg.read()), dtype=np.uint8)
            bg_image = cv2.imdecode(file_bytes, 1)
    
    # Show uploaded background preview
        if effect == "replace" and bg_image is not None:
            with col3:
                st.markdown("Uploaded Image")
                st.image(
                    bg_image,
                    caption=uploaded_bg.name,
                    use_container_width=True
                )

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
                process_video(file_path, output_path, effect, bg_image,blur_strength, progress_callback=update_progress)

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