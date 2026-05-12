import sys
from pathlib import Path

# Fix import path
ROOT_DIR = Path(__file__).resolve().parent
if ROOT_DIR.name == "app":
    ROOT_DIR = ROOT_DIR.parent
sys.path.append(str(ROOT_DIR))

import streamlit as st

from ui.state import (
    initialize_session_state,
    reset_and_clear_all,
)

from ui.uploader import (
    save_uploaded_file,
    render_video_uploader,
)

from ui.controls import (
    render_effect_controls,
)

from ui.preview import (
    show_video_comparison,
    show_background_preview,
    show_download_button,
    show_uploaded_video_preview,
)

from ui.processing import (
    render_process_button,
    show_processing_complete,
    handle_video_processing,
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

    render_process_button()

    show_processing_complete()

    if st.session_state.is_processing:
        handle_video_processing(
            file_path=file_path,
            temp_dir=TEMP_DIR,
            effect=effect,
            bg_image=bg_image,
            blur_strength=blur_strength,
        )

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
