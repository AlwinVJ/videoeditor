from pathlib import Path
import streamlit as st

from app.ui.state import AppState, set_state


def show_uploaded_video_preview(file_path, col1):
    """
    Display the uploaded input video with its extracted metadata.
    Streams directly from disk to enable browser progressive range requests.
    """
    with col1:
        st.markdown("### Uploaded Video")
        if file_path and Path(file_path).exists():
            st.video(str(file_path))

        metadata = st.session_state.get("video_metadata", {})
        if metadata:
            w = metadata.get("width", 0)
            h = metadata.get("height", 0)
            fps = metadata.get("fps", 0)
            dur = metadata.get("duration", 0)
            st.caption(f"Resolution: {w}x{h} | Duration: {dur}s | FPS: {fps}")
        elif file_path:
            st.success(f"File saved: {Path(file_path).name}")


def show_video_comparison(original_video_path, processed_video_path, col1, col2):
    """
    Display side-by-side comparison of original and processed videos.
    Both players stream progressive byte ranges from disk.
    """
    orig_path = Path(original_video_path) if original_video_path else None
    proc_path = Path(processed_video_path) if processed_video_path else None

    with col1:
        st.subheader("Original Video")
        if orig_path and orig_path.exists():
            st.video(str(orig_path))
        else:
            st.info("Original video is unavailable.")

    with col2:
        st.subheader("Processed Video")
        if proc_path and proc_path.exists() and proc_path.stat().st_size > 0:
            st.video(str(proc_path))
        else:
            st.warning("Processed video file is not available on disk.")


def show_background_preview(bg_image, uploaded_bg, col3):
    """Preview uploaded replacement background image."""
    if bg_image is not None and uploaded_bg:
        with col3:
            st.markdown("Uploaded Image")
            st.image(bg_image, caption=uploaded_bg.name, use_container_width=True)


def show_download_button(video_path):
    """
    Render download button using a deferred callable.
    Prevents Streamlit from serializing large multi-megabyte video files into the
    WebSocket message during initial preview render.
    """
    if not video_path:
        return

    path_obj = Path(video_path)
    if not path_obj.exists() or path_obj.stat().st_size == 0:
        st.warning("Processed output file is not available for download.")
        return

    def get_video_download_bytes() -> bytes:
        """Executed lazily only when the user clicks Download."""
        if st.session_state.get("app_state") in (AppState.COMPLETED, AppState.PREVIEW):
            set_state(AppState.EXPORTED)
        with open(path_obj, "rb") as fh:
            return fh.read()

    st.download_button(
        label="Download Processed Video",
        data=get_video_download_bytes,
        file_name=f"processed_{path_obj.name}",
        mime="video/mp4",
        key="download_processed_video_btn",
    )
