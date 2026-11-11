import html
from pathlib import Path
import shutil
import uuid
import streamlit as st

from core.utils import generate_safe_filename, get_file_fingerprint
from core.video_io import get_video_metadata
from core.transcription import transcribe_video, format_segment_time


def save_broll_upload(uploaded_file, temp_dir: Path) -> Path:
    """
    Save an uploaded B-roll video using chunked streaming without side effects on Editor state.
    Reuses existing files on disk across Streamlit reruns.
    """
    fingerprint = get_file_fingerprint(uploaded_file.name, uploaded_file.size)
    cached_path = st.session_state.get("broll_uploaded_path")
    cached_id = st.session_state.get("broll_uploaded_file_id")

    if cached_id == fingerprint and cached_path and Path(cached_path).exists():
        return Path(cached_path)

    safe_name = f"broll_{generate_safe_filename(uploaded_file.name)}"
    file_path = temp_dir / safe_name

    uploaded_file.seek(0)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f, length=1024 * 1024)

    st.session_state.broll_uploaded_file_id = fingerprint
    st.session_state.broll_uploaded_path = str(file_path)
    st.session_state.broll_input_video = str(file_path)
    st.session_state.broll_source = "uploaded"

    try:
        meta = get_video_metadata(file_path)
        st.session_state.broll_video_metadata = meta
    except Exception:
        st.session_state.broll_video_metadata = {}

    if file_path not in st.session_state.temp_files:
        st.session_state.temp_files.append(file_path)

    return file_path


def render_broll_page(temp_dir: Path = None):
    """
    Render the dedicated AI B-roll Editor workspace adhering strictly
    to the reference UI design:
    - Header: 'AI B-roll Editor' with subtitle and 'How It Works' button
    - Input Video Section:
        Option A: Processed Video Detected (green indicator, preview button)
        OR divider
        Option B: Upload a Video (drag-and-drop / Choose Video)
    - Preview Player (if active/requested)
    - 4 Workflow Cards (Single-Column Vertical Layout):
        Card 1: Video Transcription (Groq Whisper)
        Card 2: AI Keyword Generation (Planned: Groq LLM)
        Card 3: Stock Footage Search (Pixabay / Pexels)
        Card 4: B-roll Placement & Timeline (Planned: FFmpeg Overlay)
    """
    if temp_dir is None:
        temp_dir = Path("temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 1. PAGE HEADER
    # =========================================================================
    hdr_col1, hdr_col2 = st.columns([0.82, 0.18])
    with hdr_col1:
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px;">
                <div style="font-size: 32px; line-height: 1;">🎬</div>
                <div>
                    <div style="font-size: 1.45rem; font-weight: 700; color: #ffffff; letter-spacing: -0.01em;">AI B-roll Editor</div>
                    <div style="font-size: 0.82rem; color: #8b90a7; margin-top: 2px;">
                        Transcribe your video, generate stock footage keywords, search relevant clips, and add B-rolls to your video.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hdr_col2:
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        if st.button("How It Works ❔", key="broll_how_it_works_btn", use_container_width=True):
            st.session_state.show_broll_help = not st.session_state.get("show_broll_help", False)
            st.rerun()

    # Expandable "How It Works" Guide
    if st.session_state.get("show_broll_help", False):
        st.markdown(
            """
            <div class="editor-card" style="border: 1px solid #6c5ce7; background: rgba(108, 92, 231, 0.08); padding: 18px 24px; margin-bottom: 20px;">
                <div style="font-size: 0.95rem; font-weight: 600; color: #ffffff; margin-bottom: 8px;">🎬 How AI B-roll Editing Works</div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 12px;">
                    <div>
                        <div style="color: #a78bfa; font-weight: 600; font-size: 0.85rem;">1. Transcription</div>
                        <div style="font-size: 0.78rem; color: #8b90a7; margin-top: 4px;">Audio is transcribed into timestamped segments using Groq Whisper.</div>
                    </div>
                    <div>
                        <div style="color: #a78bfa; font-weight: 600; font-size: 0.85rem;">2. AI Keywords</div>
                        <div style="font-size: 0.78rem; color: #8b90a7; margin-top: 4px;">Groq LLM extracts context queries for each sentence.</div>
                    </div>
                    <div>
                        <div style="color: #34d399; font-weight: 600; font-size: 0.85rem;">3. Stock Search</div>
                        <div style="font-size: 0.78rem; color: #8b90a7; margin-top: 4px;">High-resolution stock video clips are retrieved from Pixabay/Pexels.</div>
                    </div>
                    <div>
                        <div style="color: #a78bfa; font-weight: 600; font-size: 0.85rem;">4. B-roll Overlay</div>
                        <div style="font-size: 0.78rem; color: #8b90a7; margin-top: 4px;">FFmpeg stitches and overlays the B-roll clips onto your video.</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # =========================================================================
    # 2. DETECT TRANSFERRED OR ACTIVE VIDEO
    # =========================================================================
    editor_processed = st.session_state.get("processed_video")
    has_processed = bool(
        editor_processed
        and Path(editor_processed).exists()
        and Path(editor_processed).stat().st_size > 0
    )

    current_broll_video = st.session_state.get("broll_input_video")
    if current_broll_video and not Path(current_broll_video).exists():
        # Clean up stale/invalid path
        st.session_state.broll_input_video = None
        current_broll_video = None

    # Automatically synchronize transferred video from editor if not overridden
    if not current_broll_video and has_processed:
        st.session_state.broll_input_video = str(editor_processed)
        st.session_state.broll_source = "transferred"
        current_broll_video = str(editor_processed)

    # Track video identity (fingerprint) to automatically invalidate old transcripts
    current_video_id = None
    if current_broll_video and Path(current_broll_video).exists():
        stat_info = Path(current_broll_video).stat()
        current_video_id = f"{current_broll_video}_{stat_info.st_size}_{stat_info.st_mtime}"

    cached_video_id = st.session_state.get("broll_transcript_video_id")
    if cached_video_id and cached_video_id != current_video_id:
        st.session_state.broll_transcript = None
        st.session_state.broll_transcript_video_id = None
        st.session_state.broll_transcription_error = None
    if current_video_id and st.session_state.get("broll_transcription_error") == "Please select or upload a video before creating a transcript.":
        st.session_state.broll_transcription_error = None

    # =========================================================================
    # 3. INPUT VIDEO SECTION CARD
    # =========================================================================
    st.markdown(
        """
        <div class="editor-card" style="padding: 20px 24px; margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
                <span style="font-size: 1.1rem; color: #a78bfa;">▶</span>
                <span style="font-size: 1.05rem; font-weight: 600; color: #ffffff;">Input Video</span>
            </div>
            <div style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 16px;">
                Use the processed video from the Editor or upload a new video to continue.
            </div>
        """,
        unsafe_allow_html=True,
    )

    col_opt_a, col_or_div, col_opt_b = st.columns([0.47, 0.06, 0.47])

    # Option A: Processed Video Detected
    with col_opt_a:
        if has_processed:
            proc_sub_col1, proc_sub_col2 = st.columns([0.72, 0.28])
            with proc_sub_col1:
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; gap: 14px; background: rgba(16, 185, 129, 0.06); border: 1px solid #10b981; border-radius: 10px; padding: 14px 16px;">
                        <div style="width: 32px; height: 32px; border-radius: 50%; background: #10b981; display: flex; align-items: center; justify-content: center; color: #0b0d14; font-weight: bold; font-size: 16px; flex-shrink: 0;">
                            ✓
                        </div>
                        <div>
                            <div style="font-size: 0.92rem; font-weight: 600; color: #10b981;">Processed Video Detected</div>
                            <div style="font-size: 0.78rem; color: #8b90a7; margin-top: 2px;">The video from the Editor is ready to use.</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with proc_sub_col2:
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                is_transferred_preview = (
                    st.session_state.get("broll_preview_active", False)
                    and st.session_state.get("broll_source") == "transferred"
                )
                preview_btn_label = "⏹  Close" if is_transferred_preview else "▷  Preview"
                if st.button(
                    preview_btn_label,
                    key="broll_preview_processed_btn",
                    use_container_width=True,
                ):
                    st.session_state.broll_input_video = str(editor_processed)
                    st.session_state.broll_source = "transferred"
                    st.session_state.broll_preview_active = not is_transferred_preview
                    st.rerun()
        else:
            st.markdown(
                """
                <div style="display: flex; align-items: center; gap: 14px; background: rgba(31, 35, 54, 0.3); border: 1px dashed #282d44; border-radius: 10px; padding: 14px 16px;">
                    <div style="width: 32px; height: 32px; border-radius: 50%; background: rgba(107, 114, 128, 0.15); display: flex; align-items: center; justify-content: center; color: #6b7280; font-size: 15px; flex-shrink: 0;">
                        🎬
                    </div>
                    <div>
                        <div style="font-size: 0.90rem; font-weight: 500; color: #9ca3af;">No Processed Video Detected</div>
                        <div style="font-size: 0.76rem; color: #6b7280; margin-top: 2px;">Process a video in the Editor tab or upload directly.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Middle Divider: OR
    with col_or_div:
        st.markdown(
            """
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; min-height: 60px;">
                <div style="width: 32px; height: 32px; border-radius: 50%; background: #12141e; border: 1px solid #282d44; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; color: #8b90a7;">
                    OR
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Option B: Upload a Video
    with col_opt_b:
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                <div>
                    <span style="font-size: 0.88rem; font-weight: 600; color: #f1f2f6;">Upload a Video</span>
                    <span style="font-size: 0.76rem; color: #6b7280; margin-left: 8px;">Drag and drop or click to browse</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        broll_uploaded = st.file_uploader(
            "Choose Video",
            type=["mp4", "mov", "avi"],
            key=st.session_state.get("broll_uploader_key", "broll_uploader_init"),
            label_visibility="collapsed",
        )

        if broll_uploaded:
            saved_broll_p = save_broll_upload(broll_uploaded, temp_dir)
            st.session_state.broll_input_video = str(saved_broll_p)
            st.session_state.broll_source = "uploaded"
            st.session_state.broll_preview_active = True

            broll_chip_col1, broll_chip_col2 = st.columns([0.88, 0.12])
            with broll_chip_col1:
                size_mb = broll_uploaded.size / (1024 * 1024)
                st.markdown(
                    f"""
                    <div style="font-size: 0.78rem; color: #34d399; margin-top: 4px;">
                        ✓ Ready: <b>{broll_uploaded.name}</b> ({size_mb:.1f} MB)
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with broll_chip_col2:
                if st.button("🗑️", key="broll_remove_upload_btn", help="Clear uploaded video"):
                    st.session_state.broll_uploaded_file_id = None
                    st.session_state.broll_uploaded_path = None
                    st.session_state.broll_uploader_key = str(uuid.uuid4())[:8]
                    if has_processed:
                        st.session_state.broll_input_video = str(editor_processed)
                        st.session_state.broll_source = "transferred"
                    else:
                        st.session_state.broll_input_video = None
                        st.session_state.broll_source = None
                    st.session_state.broll_preview_active = False
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)  # Close Input Video Card

    # =========================================================================
    # 4. VIDEO PREVIEW (if active/requested)
    # =========================================================================
    active_video = st.session_state.get("broll_input_video")
    if (
        st.session_state.get("broll_preview_active", False)
        and active_video
        and Path(active_video).exists()
    ):
        source_label = "Transferred from Editor" if st.session_state.get("broll_source") == "transferred" else "Uploaded Video"
        st.markdown(
            f"""
            <div class="editor-card" style="padding: 18px 24px; margin-bottom: 20px;">
                <div class="editor-card-header">
                    <div class="card-title-group">
                        <div class="card-title-text">B-roll Target Video Preview</div>
                    </div>
                    <span style="font-size: 0.72rem; padding: 3px 8px; border-radius: 6px; background: rgba(124, 92, 252, 0.15); color: #a78bfa; border: 1px solid rgba(124, 92, 252, 0.3);">{source_label}</span>
                </div>
            """,
            unsafe_allow_html=True,
        )
        st.video(str(active_video))
        st.markdown("</div>", unsafe_allow_html=True)

    # =========================================================================
    # 5. FOUR WORKFLOW SECTIONS (Single-Column Vertical Layout)
    # 1. Video Transcription
    # 2. AI Keyword Generation
    # 3. Stock Footage Search
    # 4. B-roll Placement & Timeline
    # =========================================================================

    # -------------------------------------------------------------------------
    # STEP 1: Video Transcription
    # -------------------------------------------------------------------------
    with st.container(key="broll_transcription_card", border=True):
        c1_head_col1, c1_head_col2 = st.columns([0.78, 0.22])
        with c1_head_col1:
            st.markdown(
                """
                <div class="card-title-group" style="display: flex; align-items: center; min-height: 38px;">
                    <div class="card-step-badge">1</div>
                    <div class="card-title-text">Video Transcription</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c1_head_col2:
            create_transcript_clicked = st.button(
                "Create Transcript",
                key="broll_create_transcript_btn",
                type="primary",
                use_container_width=True,
            )

        st.markdown(
            """
            <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 14px;">
                Extract audio and generate timestamped transcript segments for accurate B-roll matching.
            </p>
            """,
            unsafe_allow_html=True,
        )

        has_active_video = bool(
            current_broll_video
            and Path(current_broll_video).exists()
            and Path(current_broll_video).stat().st_size > 0
        )

        if create_transcript_clicked:
            if not has_active_video:
                st.session_state.broll_transcription_error = (
                    "Please select or upload a video before creating a transcript."
                )
                st.session_state.broll_transcript = None
                st.rerun()
            else:
                with st.spinner("Transcribing video... Please wait."):
                    try:
                        segments = transcribe_video(Path(current_broll_video), temp_dir)
                        st.session_state.broll_transcript = segments
                        st.session_state.broll_transcript_video_id = current_video_id
                        st.session_state.broll_transcription_error = None
                        st.rerun()
                    except Exception as e:
                        st.session_state.broll_transcription_error = str(e)
                        st.rerun()

        err_msg = st.session_state.get("broll_transcription_error")
        if err_msg:
            st.markdown(
                f"""
                <div class="status-banner-card error" style="margin-top: 4px; margin-bottom: 12px;">
                    <div class="status-banner-icon error">✕</div>
                    <div>
                        <div class="status-banner-title">Transcription failed</div>
                        <div class="status-banner-desc">{err_msg}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        transcript = st.session_state.get("broll_transcript")

        if transcript is None:
            st.markdown(
                """
                <div style="padding-bottom: 16px;">  <!-- CHANGED -->
                    <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 26px 20px; text-align: center;">
                        <div style="font-size: 28px; margin-bottom: 8px;">🎙️</div>
                        <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">Transcript Workspace Ready</div>
                        <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Your video transcript will appear here.</div>
                    </div>
                </div>  <!-- CHANGED -->
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="status-banner-card" style="margin-top: 4px; margin-bottom: 12px; padding: 10px 14px;">
                    <div class="status-banner-icon" style="width: 26px; height: 26px; font-size: 14px;">✓</div>
                    <div>
                        <div class="status-banner-title" style="font-size: 0.84rem;">Transcription completed successfully.</div>
                        <div class="status-banner-desc" style="font-size: 0.73rem;">Extracted {len(transcript)} timestamped segment{'s' if len(transcript) != 1 else ''}.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if len(transcript) == 0:
                st.markdown(
                    """
                    <div style="padding-bottom: 16px;">  <!-- CHANGED -->
                        <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 20px; text-align: center; margin-top: 10px;">
                            <div style="font-size: 0.85rem; color: #9ca3af;">No speech detected in this video.</div>
                        </div>
                    </div>  <!-- CHANGED -->
                    """,
                    unsafe_allow_html=True,
                )
            else:
                segment_cards = []
                for seg in transcript:
                    time_label = format_segment_time(seg["start"], seg["end"])
                    safe_text = html.escape(str(seg.get("text", "")).strip())
                    segment_cards.append(
                        f'<div style="background: #10121c; border: 1px solid #1f2336; border-radius: 8px; padding: 10px 14px;">'
                        f'<div style="font-size: 0.74rem; font-weight: 600; color: #a78bfa; font-family: monospace; letter-spacing: 0.05em;">{time_label}</div>'
                        f'<div style="font-size: 0.83rem; color: #e5e7eb; margin-top: 4px; line-height: 1.4;">{safe_text}</div>'
                        f'</div>'
                    )

                transcript_html = (
                    '<div style="padding-bottom: 16px;">'  # CHANGED (opening wrapper)
                    '<div style="max-height: 280px; overflow-y: auto; padding-right: 6px; padding-bottom: 8px; display: flex; flex-direction: column; gap: 8px; margin-top: 10px;">'
                    + "".join(segment_cards)
                    + '</div>'
                    '</div>'  # CHANGED (closing wrapper)
                )
                st.markdown(transcript_html, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # CARD 2: AI Keyword Generation
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div class="editor-card">
            <div class="editor-card-header">
                <div class="card-title-group">
                    <div class="card-step-badge">2</div>
                    <div class="card-title-text">AI Keyword Generation</div>
                </div>
                <span style="font-size: 0.72rem; padding: 3px 8px; border-radius: 6px; background: rgba(124, 92, 252, 0.15); color: #a78bfa; border: 1px solid rgba(124, 92, 252, 0.3);">Generate Keywords</span>
            </div>
            <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 14px;">
                Generate context-aware visual search queries and footage suggestions for each transcript segment.
            </p>
            <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 26px 20px; text-align: center;">
                <div style="font-size: 28px; margin-bottom: 8px;">🧠</div>
                <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">AI Suggestions Ready</div>
                <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Automated keyword pills and search inputs will populate here.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------------
    # CARD 3: Stock Footage Search
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div class="editor-card">
            <div class="editor-card-header">
                <div class="card-title-group">
                    <div class="card-step-badge">3</div>
                    <div class="card-title-text">Stock Footage Search</div>
                </div>
                <span style="font-size: 0.72rem; padding: 3px 8px; border-radius: 6px; background: rgba(124, 92, 252, 0.15); color: #a78bfa; border: 1px solid rgba(124, 92, 252, 0.3);">Search Footage</span>
            </div>
            <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 14px;">
                Search free video repositories and select high-resolution B-roll clips.
            </p>
            <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 26px 20px; text-align: center;">
                <div style="font-size: 28px; margin-bottom: 8px;">🎬</div>
                <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">Footage Gallery Ready</div>
                <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Search results and clip previews will appear here.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------------
    # CARD 4: B-roll Placement & Timeline
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <div class="editor-card">
            <div class="editor-card-header">
                <div class="card-title-group">
                    <div class="card-step-badge">4</div>
                    <div class="card-title-text">B-roll Placement & Timeline</div>
                </div>
                <span style="font-size: 0.72rem; padding: 3px 8px; border-radius: 6px; background: rgba(124, 92, 252, 0.15); color: #a78bfa; border: 1px solid rgba(124, 92, 252, 0.3);">Planned: FFmpeg Overlay</span>
            </div>
            <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 14px;">
                Position selected stock clips at specific start, middle, or end timestamps.
            </p>
            <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 26px 20px; text-align: center;">
                <div style="font-size: 28px; margin-bottom: 8px;">⏱️</div>
                <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">Timeline Editor Ready</div>
                <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Multi-track visual timeline and overlay preview will render here.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
