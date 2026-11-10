import sys
from pathlib import Path

# Fix import path
ROOT_DIR = Path(__file__).resolve().parent
if ROOT_DIR.name == "app":
    ROOT_DIR = ROOT_DIR.parent
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "app"))

import streamlit as st

from ui.state import (
    AppState,
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


def run_app():
    st.set_page_config(page_title="Video Background Editor", layout="wide")

    # Handling session state
    initialize_session_state()

    # UI Header
    st.title("🎬 Video Background Editor")

    if st.button("Reset and Clear All", key="reset_clear_all_btn"):
        reset_and_clear_all(TEMP_DIR)

    uploaded_file = render_video_uploader()

    if uploaded_file:
        # File path saved idempotently (will not re-write on rerun)
        file_path = save_uploaded_file(uploaded_file, TEMP_DIR)

        # Preview original
        st.subheader("Preview")
        col1, col2, col3 = st.columns([3, 0.5, 2])
        show_uploaded_video_preview(uploaded_file, file_path, col1)

        # Effects
        effect, blur_strength, bg_image, uploaded_bg = render_effect_controls(col3)

        # Background preview
        show_background_preview(bg_image, uploaded_bg, col3)

        # Process Button & Status Banner
        process_triggered = render_process_button()
        show_processing_complete()

        # Execute processing only when explicitly triggered or in active processing state
        if process_triggered or st.session_state.app_state == AppState.PROCESSING:
            handle_video_processing(
                file_path=file_path,
                temp_dir=TEMP_DIR,
                effect=effect,
                bg_image=bg_image,
                blur_strength=blur_strength,
            )

        # Display result if completed or in preview/exported state
        if (
            st.session_state.app_state in (AppState.COMPLETED, AppState.PREVIEW, AppState.EXPORTED)
            and st.session_state.processed_video
        ):
            video_path = Path(st.session_state.processed_video)
            if video_path.exists():
                st.divider()
                st.subheader("Result")

                col_res1, col_res2 = st.columns(2)
                show_video_comparison(uploaded_file, video_path, col_res1, col_res2)

                # Download button
                show_download_button(video_path)


if __name__ == "__main__":
    run_app()
