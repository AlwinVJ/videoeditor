from pathlib import Path
import streamlit as st

from core.video_io import process_video
from core.utils import get_job_dir
from app.ui.state import AppState, set_state


def render_process_button() -> bool:
    """
    Render the process trigger button according to the current FSM state.
    Returns True if processing was triggered in this cycle.
    """
    current_state = st.session_state.get("app_state", AppState.IDLE)
    is_busy = (current_state == AppState.PROCESSING)

    button_label = "Process Video"
    if current_state in (AppState.COMPLETED, AppState.PREVIEW, AppState.EXPORTED):
        button_label = "Re-Process with Current Settings"
    elif current_state == AppState.FAILED:
        button_label = "Retry Processing"

    clicked = st.button(
        button_label,
        disabled=is_busy,
        key="process_video_action_btn",
    )

    if clicked:
        set_state(AppState.PROCESSING)
        return True

    return False


def show_processing_status():
    """Display status banners based on the current state."""
    current_state = st.session_state.get("app_state")

    if current_state in (AppState.COMPLETED, AppState.PREVIEW, AppState.EXPORTED):
        st.success("Processing complete! You can preview or download your video below.")
    elif current_state == AppState.FAILED:
        err = st.session_state.get("error_message", "An unknown error occurred.")
        st.error(f"Processing failed: {err}")


def show_processing_complete():
    """Backward-compatible helper."""
    show_processing_status()


def handle_video_processing(
    file_path: Path,
    temp_dir: Path,
    effect: str,
    bg_image,
    blur_strength: int,
):
    """
    Execute video processing within the FSM lifecycle.
    Idempotent: prevents duplicate execution for identical job parameters.
    """
    file_path = Path(file_path)

    # Compute deterministic job ID
    bg_tag = "custom_bg" if bg_image is not None else "no_bg"
    job_id = f"{file_path.stem}_{effect}_{blur_strength}_{bg_tag}"

    job_dir = get_job_dir(temp_dir, job_id)
    output_path = job_dir / f"processed_{file_path.stem}.mp4"

    # If already completed with existing file on disk, transition directly to COMPLETED
    if (
        st.session_state.get("completed_job_id") == job_id
        and output_path.exists()
        and output_path.stat().st_size > 0
    ):
        st.session_state.processed_video = str(output_path)
        set_state(AppState.COMPLETED)
        return

    progress_placeholder = st.empty()
    status_placeholder = st.empty()

    progress_bar = progress_placeholder.progress(0.0)
    status_placeholder.text("Starting video processing... 0%")

    def update_progress(progress_val: float):
        progress_bar.progress(progress_val)
        status_placeholder.text(f"Processing video... {int(progress_val * 100)}%")

    try:
        st.session_state.active_job_id = job_id
        set_state(AppState.PROCESSING)

        with st.spinner("Applying AI segmentation and video effects..."):
            process_video(
                input_path=file_path,
                output_path=output_path,
                effect=effect,
                bg_image=bg_image,
                blur_strength=blur_strength,
                progress_callback=update_progress,
            )

        progress_placeholder.empty()
        status_placeholder.empty()

        # Update session state on success
        st.session_state.processed_video = str(output_path)
        st.session_state.completed_job_id = job_id
        st.session_state.error_message = None

        if output_path not in st.session_state.temp_files:
            st.session_state.temp_files.append(output_path)

        set_state(AppState.COMPLETED)
        st.rerun()

    except Exception as e:
        progress_placeholder.empty()
        status_placeholder.empty()
        print(f"Error during video processing: {e}")
        st.session_state.error_message = str(e)
        st.session_state.completed_job_id = None
        set_state(AppState.FAILED)
        st.rerun()
    finally:
        st.session_state.active_job_id = None
