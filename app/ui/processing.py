import streamlit as st
from pathlib import Path

from core.video_io import process_video


def render_process_button():

    def start_processing():
        st.session_state.is_processing = True

    st.button(
        "Process Video",
        on_click=start_processing,
        disabled=st.session_state.is_processing,
    )


def show_processing_complete():

    if st.session_state.get(
        "processing_complete"
    ):

        st.success(
            "Processing complete!"
        )

        st.session_state.processing_complete = (
            False
        )


def handle_video_processing(
    file_path,
    temp_dir: Path,
    effect,
    bg_image,
    blur_strength
):

    output_path = (
        temp_dir /
        f"processed_{file_path.stem}.mp4"
    )

    progress_bar = st.progress(0)

    status_text = st.empty()

    status_text.text(
        "Processing video... 0%"
    )

    def update_progress(progress):

        progress_bar.progress(
            progress
        )

        status_text.text(
            f"Processing video... "
            f"{int(progress * 100)}%"
        )

    try:

        with st.spinner(
            "Making changes ..."
        ):

            process_video(
                file_path,
                output_path,
                effect,
                bg_image,
                blur_strength,
                progress_callback=(
                    update_progress
                ),
            )

        progress_bar.empty()
        status_text.empty()

        st.session_state.processing_complete = (
            True
        )

        # Save processed path
        st.session_state.processed_video = (
            str(output_path)
        )

        if (
            output_path
            not in
            st.session_state.temp_files
        ):

            st.session_state.temp_files.append(
                output_path
            )

    finally:

        st.session_state.is_processing = (
            False
        )

        # st.rerun()