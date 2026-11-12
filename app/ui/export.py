from pathlib import Path
import streamlit as st
from app.ui.state import AppState, set_state


def render_export_page():
    """
    Render the dedicated Export workspace:
    - Processed video preview
    - File details (filename, size, resolution, duration)
    - Direct deferred download button
    - Completion status
    """
    st.markdown(
        """
        <div class="page-header-container">
            <div class="header-icon-box" style="color: #10b981;">
                📥
            </div>
            <div>
                <div class="header-text-title">Export Video</div>
                <div class="header-text-desc">Review your final rendered video and download the high-resolution output.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    processed_path_str = st.session_state.get("processed_video")
    has_processed = (
        processed_path_str
        and Path(processed_path_str).exists()
        and Path(processed_path_str).stat().st_size > 0
    )

    if not has_processed:
        st.markdown(
            """
            <div class="editor-card" style="text-align: center; padding: 48px 24px;">
                <div style="font-size: 40px; margin-bottom: 12px;">🎬</div>
                <div style="font-size: 1.1rem; font-weight: 600; color: #ffffff;">No Processed Video Available</div>
                <p style="font-size: 0.85rem; color: #8b90a7; max-width: 460px; margin: 8px auto 20px auto;">
                    Please go to the <b>Editor</b> tab or <b>AI B-roll</b> tab, upload or process a video, and render your output.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_ret1, col_ret2 = st.columns(2)
        with col_ret1:
            if st.button("← Return to Editor", key="export_no_proc_editor_btn", type="primary", use_container_width=True):
                st.session_state.current_page = "editor"
                st.rerun()
        with col_ret2:
            if st.button("← Return to AI B-roll", key="export_no_proc_broll_btn", type="secondary", use_container_width=True):
                st.session_state.current_page = "broll"
                st.rerun()
        return

    if st.session_state.get("broll_generation_success"):
        st.markdown(
            """
            <div class="status-banner-card" style="margin-bottom: 20px; padding: 12px 16px; border-left: 4px solid #10b981;">
                <div class="status-banner-icon" style="color: #10b981; font-weight: bold; width: 26px; height: 26px; font-size: 14px;">✓</div>
                <div>
                    <div class="status-banner-title" style="color: #ffffff; font-weight: 600; font-size: 0.90rem;">B-roll Video Generated Successfully!</div>
                    <div class="status-banner-desc" style="color: #9ca3af; font-size: 0.78rem;">Your selected stock footage cutaways have been placed onto the timeline. Review the preview and download your video below.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    proc_path = Path(processed_path_str)
    file_size_mb = proc_path.stat().st_size / (1024 * 1024)
    meta = st.session_state.get("video_metadata", {})
    w = meta.get("width", "—")
    h = meta.get("height", "—")
    dur = meta.get("duration", "—")
    fps = meta.get("fps", "—")

    col_prev, col_details = st.columns([0.62, 0.38], gap="large")

    with col_prev:
        st.markdown(
            """
            <div class="editor-card">
                <div class="editor-card-header">
                    <div class="card-title-group">
                        <div class="card-title-text">Rendered Video Preview</div>
                    </div>
                    <span style="font-size: 0.72rem; padding: 3px 8px; border-radius: 6px; background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3);">Ready for Export</span>
                </div>
            """,
            unsafe_allow_html=True,
        )

        st.video(str(proc_path))
        st.markdown("</div>", unsafe_allow_html=True)

    with col_details:
        st.markdown(
            f"""
            <div class="editor-card">
                <div class="editor-card-header">
                    <div class="card-title-group">
                        <div class="card-title-text">File Details</div>
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; gap: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; border-bottom: 1px solid #1f2336; padding-bottom: 8px;">
                        <span style="color: #8b90a7;">File Name:</span>
                        <span style="color: #f1f2f6; font-weight: 500;">{proc_path.name}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; border-bottom: 1px solid #1f2336; padding-bottom: 8px;">
                        <span style="color: #8b90a7;">File Size:</span>
                        <span style="color: #f1f2f6; font-weight: 500;">{file_size_mb:.2f} MB</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; border-bottom: 1px solid #1f2336; padding-bottom: 8px;">
                        <span style="color: #8b90a7;">Resolution:</span>
                        <span style="color: #f1f2f6; font-weight: 500;">{w}x{h}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; border-bottom: 1px solid #1f2336; padding-bottom: 8px;">
                        <span style="color: #8b90a7;">Duration:</span>
                        <span style="color: #f1f2f6; font-weight: 500;">{dur}s</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; border-bottom: 1px solid #1f2336; padding-bottom: 8px;">
                        <span style="color: #8b90a7;">Framerate:</span>
                        <span style="color: #f1f2f6; font-weight: 500;">{fps} FPS</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                        <span style="color: #8b90a7;">Format & Codec:</span>
                        <span style="color: #f1f2f6; font-weight: 500;">MP4 (H.264 / AAC)</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        def get_export_bytes() -> bytes:
            if st.session_state.get("app_state") in (AppState.COMPLETED, AppState.PREVIEW):
                set_state(AppState.EXPORTED)
            with open(proc_path, "rb") as fh:
                return fh.read()

        st.download_button(
            label="Download Processed Video",
            data=get_export_bytes,
            file_name=f"exported_{proc_path.name}",
            mime="video/mp4",
            type="primary",
            use_container_width=True,
            key="export_page_download_btn",
        )

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        col_nav1, col_nav2 = st.columns(2)
        with col_nav1:
            if st.button("← AI B-roll", key="export_return_broll_btn", use_container_width=True):
                st.session_state.current_page = "broll"
                st.rerun()
        with col_nav2:
            if st.button("← Main Editor", key="export_return_editor_btn", use_container_width=True):
                st.session_state.current_page = "editor"
                st.rerun()
