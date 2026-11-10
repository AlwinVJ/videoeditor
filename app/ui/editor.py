from pathlib import Path
import streamlit as st
import cv2
import numpy as np

from app.ui.state import AppState, set_state
from app.ui.uploader import save_uploaded_file
from core.video_io import process_video, get_video_metadata
from core.utils import get_job_dir, safe_unlink


def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    if not seconds or seconds <= 0:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def render_editor_page(temp_dir: Path):
    """
    Render the main editor page adhering strictly to the reference UI layout:
    - Left Column: Upload Video & Edit Settings
    - Right Column: Preview, Processing Status, and Primary Action Buttons
    """
    # Page Header matching reference image
    st.markdown(
        """
        <style>

        /* Move the complete editor workspace upward */
        section[data-testid="stMain"] .block-container {
            padding-top: 5rem !important;
            padding-bottom: 1rem !important;
        }

        /* Reduce header spacing */
        .page-header-container {
            margin-top: -0.5rem !important;
            margin-bottom: 1rem !important;
        }

        /* Compact editor cards */
        .editor-card {
            padding: 14px 18px !important;
            margin-bottom: 12px !important;
        }

        /* Reduce spacing between Streamlit elements */
        div[data-testid="stVerticalBlock"] {
            gap: 0.75rem;
        }

        /* Reduce unnecessary space around video previews */
        div[data-testid="stVideo"] {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }

        /* Compact processing status */
        .status-banner-card {
            margin-top: 8px !important;
            margin-bottom: 8px !important;
        }

        </style>
        <div class="page-header-container">
            <div class="header-icon-box">
                🎬
            </div>
            <div>
                <div class="header-text-title">Video Editor</div>
                <div class="header-text-desc">Edit your video, apply background effects, and enhance it with AI tools.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([0.44, 0.56], gap="large")

    # =========================================================================
    # LEFT COLUMN: ① Upload Video & ② Edit Settings
    # =========================================================================
    with col_left:
        # Card 1: Upload Video
        st.markdown(
            """
            <div class="editor-card">
                <div class="editor-card-header">
                    <div class="card-title-group">
                        <div class="card-step-badge">1</div>
                        <div class="card-title-text">Upload Video</div>
                    </div>
                </div>
            """,
            unsafe_allow_html=True,
        )

        uploaded_video = st.file_uploader(
            "Upload your video",
            type=["mp4", "mov", "avi"],
            key=st.session_state.uploader_key,
            label_visibility="collapsed",
        )

        # Handle uploaded video caching and metadata
        file_path = None
        if uploaded_video:
            file_path = save_uploaded_file(uploaded_video, temp_dir)
            st.session_state.uploaded_file_name = uploaded_video.name
            st.session_state.uploaded_file_size = uploaded_video.size

            # Display uploaded video info chip with trash can
            meta = st.session_state.get("video_metadata", {})
            size_mb = st.session_state.uploaded_file_size / (1024 * 1024)
            dur_str = format_duration(meta.get("duration", 0))

            chip_col1, chip_col2 = st.columns([0.88, 0.12])
            with chip_col1:
                st.markdown(
                    f"""
                    <div class="file-info-chip">
                        <div class="file-info-left">
                            <div class="file-thumb-icon">▶</div>
                            <div>
                                <div class="file-name-text">{st.session_state.uploaded_file_name}</div>
                                <div class="file-meta-text">{size_mb:.1f} MB • {dur_str}</div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with chip_col2:
                st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
                if st.button("🗑️", key="remove_uploaded_video_btn", help="Remove video"):
                    st.session_state.uploaded_file_id = None
                    st.session_state.input_video_path = None
                    st.session_state.processed_video = None
                    st.session_state.video_metadata = {}
                    set_state(AppState.IDLE)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)  # Close Card 1

        # Card 2: Edit Settings
        st.markdown(
            """
            <div class="editor-card">
                <div class="editor-card-header">
                    <div class="card-title-group">
                        <div class="card-step-badge">2</div>
                        <div class="card-title-text">Edit Settings</div>
                    </div>
                </div>
            """,
            unsafe_allow_html=True,
        )

        is_busy = (st.session_state.get("app_state") == AppState.PROCESSING)

        effect_labels = ["Replace Background", "Blur Background", "White Background", "None"]
        current_effect_idx = effect_labels.index(st.session_state.get("selected_effect", "Replace Background"))

        selected_effect_label = st.selectbox(
            "Effect",
            effect_labels,
            index=current_effect_idx,
            disabled=is_busy,
            key="effect_selector_widget",
        )
        st.session_state.selected_effect = selected_effect_label

        effect_map = {
            "Replace Background": "replace",
            "Blur Background": "blur",
            "White Background": "white",
            "None": "none",
        }
        effect_code = effect_map[selected_effect_label]

        # Background Image Uploader (if Replace Background selected)
        bg_image_cv = None
        if effect_code == "replace":
            st.markdown("<div style='margin-top: 10px; font-size: 0.88rem; font-weight: 500; color: #d1d5db;'>Background Image</div>", unsafe_allow_html=True)
            uploaded_bg = st.file_uploader(
                "Upload Background Image",
                type=["jpg", "png", "jpeg"],
                key="bg_image_uploader_widget",
                label_visibility="collapsed",
                disabled=is_busy,
            )

            if uploaded_bg:
                file_bytes = np.asarray(bytearray(uploaded_bg.read()), dtype=np.uint8)
                bg_image_cv = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                st.session_state.bg_image_name = uploaded_bg.name
                st.session_state.bg_image_size = uploaded_bg.size

                bg_chip_col1, bg_chip_col2, bg_chip_col3 = st.columns([0.70, 0.12, 0.18])
                with bg_chip_col1:
                    bg_mb = uploaded_bg.size / (1024 * 1024)
                    st.markdown(
                        f"""
                        <div class="file-info-chip" style="margin-top: 4px;">
                            <div class="file-info-left">
                                <div class="file-thumb-icon">🖼️</div>
                                <div>
                                    <div class="file-name-text">{uploaded_bg.name}</div>
                                    <div class="file-meta-text">{bg_mb:.1f} MB</div>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with bg_chip_col2:
                    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️", key="remove_bg_image_btn", help="Remove image"):
                        st.session_state.bg_image_name = None
                        st.session_state.bg_image_size = 0
                        st.rerun()
                with bg_chip_col3:
                    if bg_image_cv is not None:
                        st.image(bg_image_cv, use_container_width=True)

        # Blur Strength Selector
        blur_strength_val = 51
        if effect_code == "blur":
            st.markdown("<div style='margin-top: 10px; font-size: 0.88rem; font-weight: 500; color: #d1d5db;'>Blur Strength</div>", unsafe_allow_html=True)
            blur_options = ["Light", "Medium", "Strong"]
            curr_blur_idx = blur_options.index(st.session_state.get("blur_option", "Medium"))
            selected_blur_opt = st.select_slider(
                "Blur Strength",
                options=blur_options,
                value=blur_options[curr_blur_idx],
                disabled=is_busy,
                key="blur_strength_slider_widget",
                label_visibility="collapsed",
            )
            st.session_state.blur_option = selected_blur_opt
            blur_strength_val = {"Light": 21, "Medium": 51, "Strong": 101}[selected_blur_opt]

        st.markdown("</div>", unsafe_allow_html=True)  # Close Card 2

    # =========================================================================
    # RIGHT COLUMN: ③ Preview, ④ Processing, ⑤ Actions
    # =========================================================================
    with col_right:
        # Card 3: Preview
        preview_mode = st.session_state.get("preview_mode", "comparison")

        prev_header_col1, prev_header_col2 = st.columns([0.60, 0.40])
        with prev_header_col1:
            st.markdown(
                """
                <div class="card-title-group" style="margin-top: 4px;">
                    <div class="card-step-badge">3</div>
                    <div class="card-title-text">Preview</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with prev_header_col2:
            toggle_col1, toggle_col2 = st.columns(2)
            with toggle_col1:
                is_comp = (preview_mode == "comparison")
                if st.button(
                    "Comparison",
                    key="toggle_comparison_btn",
                    type="primary" if is_comp else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.preview_mode = "comparison"
                    st.rerun()
            with toggle_col2:
                is_proc = (preview_mode == "processed_only")
                if st.button(
                    "Processed Only",
                    key="toggle_processed_only_btn",
                    type="primary" if is_proc else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.preview_mode = "processed_only"
                    st.rerun()

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        # Video Player Rendering Container
        input_path = st.session_state.get("input_video_path")
        processed_path = st.session_state.get("processed_video")
        has_input = (input_path and Path(input_path).exists())
        has_processed = (processed_path and Path(processed_path).exists() and Path(processed_path).stat().st_size > 0)

        if preview_mode == "comparison":
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                st.markdown("<span style='font-size: 0.78rem; font-weight: 600; color: #9ca3af;'>Original</span>", unsafe_allow_html=True)
                if has_input:
                    st.video(str(input_path))
                else:
                    st.info("Upload a video to view original.")
            with col_v2:
                st.markdown("<span style='font-size: 0.78rem; font-weight: 600; color: #a78bfa;'>Processed</span>", unsafe_allow_html=True)
                if has_processed:
                    st.video(str(processed_path))
                elif has_input:
                    st.info("Click 'Process Video' to generate preview.")
                else:
                    st.info("Processed video will appear here.")
        else:
            # Processed Only mode
            st.markdown("<span style='font-size: 0.78rem; font-weight: 600; color: #a78bfa;'>Processed</span>", unsafe_allow_html=True)
            if has_processed:
                st.video(str(processed_path))
            elif has_input:
                st.info("Click 'Process Video' below to generate the processed output.")
            else:
                st.info("Upload and process a video to preview.")

        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

        # Card 4: Processing Status
        st.markdown(
            """
            <div class="editor-card" style="padding: 16px 20px; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                    <div style="display: flex; align-items: center; gap: 8px; font-size: 0.92rem; font-weight: 600; color: #ffffff;">
                        <span>⚙️</span> Processing
                    </div>
                </div>
            """,
            unsafe_allow_html=True,
        )

        app_state = st.session_state.get("app_state", AppState.IDLE)
        progress_val = st.session_state.get("processing_progress", 0.0)

        # Progress bar
        st.progress(progress_val)

        # Status Banner
        if app_state in (AppState.COMPLETED, AppState.PREVIEW, AppState.EXPORTED):
            st.markdown(
                """
                <div class="status-banner-card">
                    <div class="status-banner-icon">✓</div>
                    <div>
                        <div class="status-banner-title">Processing complete!</div>
                        <div class="status-banner-desc">Your video is ready to preview and download.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif app_state == AppState.PROCESSING:
            st.markdown(
                f"""
                <div class="status-banner-card processing">
                    <div class="status-banner-icon processing">⏳</div>
                    <div>
                        <div class="status-banner-title">Processing video... {int(progress_val * 100)}%</div>
                        <div class="status-banner-desc">Applying AI background segmentation and effects.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif app_state == AppState.FAILED:
            err_msg = st.session_state.get("error_message", "Unknown error")
            st.markdown(
                f"""
                <div class="status-banner-card error">
                    <div class="status-banner-icon error">✕</div>
                    <div>
                        <div class="status-banner-title">Processing failed</div>
                        <div class="status-banner-desc">{err_msg}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)  # Close Card 4

        # Card 5: Primary Actions
        action_col1, action_col2 = st.columns(2)

        # Trigger Processing Button
        with action_col1:
            process_btn_disabled = (not has_input) or (app_state == AppState.PROCESSING)
            if st.button(
                "▷  Process Video",
                type="primary",
                disabled=process_btn_disabled,
                use_container_width=True,
                key="primary_process_video_action_btn",
            ):
                # Execute processing
                input_file_p = Path(st.session_state.input_video_path)
                bg_tag = "custom_bg" if bg_image_cv is not None else "no_bg"
                job_id = f"{input_file_p.stem}_{effect_code}_{blur_strength_val}_{bg_tag}"
                job_dir = get_job_dir(temp_dir, job_id)
                output_p = job_dir / f"processed_{input_file_p.stem}.mp4"

                progress_placeholder = st.empty()
                status_placeholder = st.empty()

                def on_progress(p):
                    st.session_state.processing_progress = p

                try:
                    set_state(AppState.PROCESSING)
                    st.session_state.processing_progress = 0.0

                    with st.spinner("Processing video..."):
                        process_video(
                            input_path=input_file_p,
                            output_path=output_p,
                            effect=effect_code,
                            bg_image=bg_image_cv,
                            blur_strength=blur_strength_val,
                            progress_callback=on_progress,
                        )

                    st.session_state.processing_progress = 1.0
                    st.session_state.processed_video = str(output_p)
                    st.session_state.completed_job_id = job_id
                    st.session_state.error_message = None
                    set_state(AppState.COMPLETED)
                    st.rerun()

                except Exception as e:
                    print(f"Processing error: {e}")
                    st.session_state.error_message = str(e)
                    set_state(AppState.FAILED)
                    st.rerun()

        # Download Video Button (Deferred Callable)
        with action_col2:
            download_disabled = not has_processed

            def get_download_data() -> bytes:
                set_state(AppState.EXPORTED)
                with open(processed_path, "rb") as fh:
                    return fh.read()

            out_filename = f"processed_{Path(processed_path).name}" if has_processed else "processed_video.mp4"

            st.download_button(
                label="📥  Download Video",
                data=get_download_data if has_processed else b"",
                file_name=out_filename,
                mime="video/mp4",
                disabled=download_disabled,
                use_container_width=True,
                key="primary_download_video_action_btn",
            )
