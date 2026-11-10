from pathlib import Path
import streamlit as st

from app.ui.state import AppState, set_state


def show_uploaded_video_preview(uploaded_file, file_path, col1):
    """Display the uploaded input video with its extracted metadata."""
    with col1:
        st.markdown("### Uploaded Video")
        st.video(uploaded_file)

        metadata = st.session_state.get("video_metadata", {})
        if metadata:
            w = metadata.get("width", 0)
            h = metadata.get("height", 0)
            fps = metadata.get("fps", 0)
            dur = metadata.get("duration", 0)
            st.caption(f"Resolution: {w}x{h} | Duration: {dur}s | FPS: {fps}")
        else:
            st.success(f"File saved: {Path(file_path).name}")


def show_video_comparison(uploaded_file, video_path, col1, col2):
    """Display side-by-side comparison of original and processed videos."""
    video_path = Path(video_path)

    with col1:
        st.subheader("Original Video")
        st.video(uploaded_file)

    with col2:
        st.subheader("Processed Video")
        if video_path.exists() and video_path.stat().st_size > 0:
            st.video(str(video_path))
        else:
            st.warning("Processed video file is not available on disk.")


def show_background_preview(bg_image, uploaded_bg, col3):
    """Preview uploaded replacement background image."""
    if bg_image is not None and uploaded_bg:
        with col3:
            st.markdown("Uploaded Image")
            st.image(bg_image, caption=uploaded_bg.name, use_container_width=True)


def show_download_button(video_path):
    """Render the download button for the completed video."""
    if not video_path:
        return

    path_obj = Path(video_path)
    if not path_obj.exists() or path_obj.stat().st_size == 0:
        st.warning("Processed output file is not available for download.")
        return

    def on_download_click():
        set_state(AppState.EXPORTED)

    with open(path_obj, "rb") as file_handle:
        st.download_button(
            label="Download Processed Video",
            data=file_handle,
            file_name=f"processed_{path_obj.name}",
            mime="video/mp4",
            on_click=on_download_click,
            key="download_processed_video_btn",
        )
