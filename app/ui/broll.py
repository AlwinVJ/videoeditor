import html
from pathlib import Path
import shutil
import uuid
import streamlit as st

from core.utils import generate_safe_filename, get_file_fingerprint
from core.video_io import get_video_metadata
from core.transcription import transcribe_video, format_segment_time
from core.keywords import generate_keywords_from_transcript
from core.stock import (
    search_stock_footage,
    search_pixabay_videos,
    match_clip_to_transcript,
    get_segment_color,
    calculate_timeline_percentages,
    calculate_clip_placements,
    format_duration,
)
from core.pipeline import compose_broll_video
from app.ui.state import AppState, set_state


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
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-top: 12px;">
                    <div>
                        <div style="color: #a78bfa; font-weight: 600; font-size: 0.85rem;">1. Transcription</div>
                        <div style="font-size: 0.78rem; color: #8b90a7; margin-top: 4px;">Audio is transcribed into timestamped segments using Groq Whisper.</div>
                    </div>
                    <div>
                        <div style="color: #a78bfa; font-weight: 600; font-size: 0.85rem;">2. AI Keywords</div>
                        <div style="font-size: 0.78rem; color: #8b90a7; margin-top: 4px;">Groq LLM extracts context queries for each sentence.</div>
                    </div>
                    <div>
                        <div style="color: #34d399; font-weight: 600; font-size: 0.85rem;">3. Suggested Footage</div>
                        <div style="font-size: 0.78rem; color: #8b90a7; margin-top: 4px;">Stock video clips are suggested based on AI keywords from Pixabay.</div>
                    </div>
                    <div>
                        <div style="color: #06b6d4; font-weight: 600; font-size: 0.85rem;">4. Manual Search</div>
                        <div style="font-size: 0.78rem; color: #8b90a7; margin-top: 4px;">Search and pick custom stock clips with your own search terms.</div>
                    </div>
                    <div>
                        <div style="color: #a78bfa; font-weight: 600; font-size: 0.85rem;">5. B-roll Overlay</div>
                        <div style="font-size: 0.78rem; color: #8b90a7; margin-top: 4px;">FFmpeg stitches and overlays all selected B-roll clips onto your video.</div>
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
        st.session_state.broll_keywords = None
        st.session_state.broll_keywords_video_id = None
        st.session_state.broll_keywords_error = None
        st.session_state.broll_stock_results = None
        st.session_state.broll_stock_video_id = None
        st.session_state.broll_stock_error = None
        st.session_state.broll_selected_clip = None
        st.session_state.broll_selected_clips = []
        st.session_state.broll_selected_clips_video_id = None
        st.session_state.broll_generation_error = None
        st.session_state.broll_generation_success = False
        st.session_state.broll_is_generating = False
    cached_keywords_video_id = st.session_state.get("broll_keywords_video_id")
    if cached_keywords_video_id and cached_keywords_video_id != current_video_id:
        st.session_state.broll_keywords = None
        st.session_state.broll_keywords_video_id = None
        st.session_state.broll_keywords_error = None
        st.session_state.broll_stock_results = None
        st.session_state.broll_stock_video_id = None
        st.session_state.broll_stock_error = None
        st.session_state.broll_selected_clip = None
        st.session_state.broll_selected_clips = []
        st.session_state.broll_selected_clips_video_id = None
        st.session_state.broll_generation_error = None
        st.session_state.broll_generation_success = False
        st.session_state.broll_is_generating = False
    cached_stock_video_id = st.session_state.get("broll_stock_video_id")
    if cached_stock_video_id and cached_stock_video_id != current_video_id:
        st.session_state.broll_stock_results = None
        st.session_state.broll_stock_video_id = None
        st.session_state.broll_stock_error = None
        st.session_state.broll_selected_clip = None
        st.session_state.broll_selected_clips = []
        st.session_state.broll_selected_clips_video_id = None
        st.session_state.broll_generation_error = None
        st.session_state.broll_generation_success = False
        st.session_state.broll_is_generating = False
    cached_manual_video_id = st.session_state.get("broll_manual_video_id")
    if cached_manual_video_id and cached_manual_video_id != current_video_id:
        st.session_state.broll_manual_results = None
        st.session_state.broll_manual_video_id = None
        st.session_state.broll_manual_error = None
        st.session_state.broll_manual_query = ""
    cached_selection_video_id = st.session_state.get("broll_selected_clips_video_id")
    if cached_selection_video_id and cached_selection_video_id != current_video_id:
        st.session_state.broll_selected_clip = None
        st.session_state.broll_selected_clips = []
        st.session_state.broll_selected_clips_video_id = None
    if current_video_id and st.session_state.get("broll_transcription_error") == "Please select or upload a video before creating a transcript.":
        st.session_state.broll_transcription_error = None
    if st.session_state.get("broll_transcript") and st.session_state.get("broll_keywords_error") == "Please generate a video transcript before generating keywords.":
        st.session_state.broll_keywords_error = None
    if st.session_state.get("broll_keywords") and st.session_state.get("broll_stock_error") == "Please generate AI keywords in Step 2 before searching for stock footage.":
        st.session_state.broll_stock_error = None

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
                    st.session_state.broll_selected_clip = None
                    st.session_state.broll_selected_clips = []
                    st.session_state.broll_selected_clips_video_id = None
                    st.session_state.broll_manual_results = None
                    st.session_state.broll_manual_query = ""
                    st.session_state.broll_manual_video_id = None
                    st.session_state.broll_manual_error = None
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
    # 5. FIVE WORKFLOW SECTIONS (Single-Column Vertical Layout)
    # 1. Video Transcription
    # 2. AI Keyword Generation
    # 3. Suggested Stock Footage
    # 4. Manual Stock Footage Search
    # 5. B-roll Placement & Timeline
    # =========================================================================

    # Calculate video duration once for timeline components across all workflow cards
    transcript = st.session_state.get("broll_transcript")
    total_video_duration = 0.0
    if current_broll_video and Path(current_broll_video).exists():
        try:
            meta = get_video_metadata(Path(current_broll_video))
            total_video_duration = float(meta.get("duration", 0.0) or 0.0)
        except Exception:
            pass
    if total_video_duration <= 0.0 and transcript:
        ends = [float(s.get("end", 0.0)) for s in transcript if isinstance(s, dict) and "end" in s]
        if ends:
            total_video_duration = max(ends)

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
    # STEP 2: AI Keyword Generation
    # -------------------------------------------------------------------------
    with st.container(key="broll_keywords_card", border=True):
        c2_head_col1, c2_head_col2 = st.columns([0.78, 0.22])
        with c2_head_col1:
            st.markdown(
                """
                <div class="card-title-group" style="display: flex; align-items: center; min-height: 38px;">
                    <div class="card-step-badge">2</div>
                    <div class="card-title-text">AI Keyword Generation</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2_head_col2:
            generate_keywords_clicked = st.button(
                "Generate Keywords",
                key="broll_generate_keywords_btn",
                type="primary",
                use_container_width=True,
            )

        st.markdown(
            """
            <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 14px;">
                Generate context-aware visual search queries and footage suggestions for each transcript segment.
            </p>
            """,
            unsafe_allow_html=True,
        )

        if generate_keywords_clicked:
            transcript = st.session_state.get("broll_transcript")
            if not transcript:
                st.session_state.broll_keywords_error = (
                    "Please generate a video transcript before generating keywords."
                )
                st.session_state.broll_keywords = None
                st.rerun()
            else:
                with st.spinner("Generating visual keywords with AI... Please wait."):
                    try:
                        keywords = generate_keywords_from_transcript(transcript)
                        st.session_state.broll_keywords = keywords
                        st.session_state.broll_keywords_video_id = current_video_id
                        st.session_state.broll_keywords_error = None
                        st.rerun()
                    except Exception as e:
                        st.session_state.broll_keywords_error = str(e)
                        st.rerun()

        kw_err_msg = st.session_state.get("broll_keywords_error")
        if kw_err_msg:
            st.markdown(
                f"""
                <div class="status-banner-card error" style="margin-top: 4px; margin-bottom: 12px;">
                    <div class="status-banner-icon error">✕</div>
                    <div>
                        <div class="status-banner-title">Keyword generation failed</div>
                        <div class="status-banner-desc">{html.escape(kw_err_msg)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        keywords = st.session_state.get("broll_keywords")

        if keywords is None:
            st.markdown(
                """
                <div style="padding-bottom: 16px;">
                    <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 26px 20px; text-align: center;">
                        <div style="font-size: 28px; margin-bottom: 8px;">🧠</div>
                        <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">AI Suggestions Ready</div>
                        <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Automated keyword pills and search inputs will populate here.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="status-banner-card" style="margin-top: 4px; margin-bottom: 12px; padding: 10px 14px;">
                    <div class="status-banner-icon" style="width: 26px; height: 26px; font-size: 14px;">✓</div>
                    <div>
                        <div class="status-banner-title" style="font-size: 0.84rem;">Keywords generated successfully.</div>
                        <div class="status-banner-desc" style="font-size: 0.73rem;">Extracted {len(keywords)} visual search keyword{'s' if len(keywords) != 1 else ''}.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if len(keywords) == 0:
                st.markdown(
                    """
                    <div style="padding-bottom: 16px;">
                        <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 20px; text-align: center; margin-top: 10px;">
                            <div style="font-size: 0.85rem; color: #9ca3af;">No visual keywords could be extracted from the transcript.</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                keyword_pills = []
                for kw in keywords:
                    safe_kw = html.escape(str(kw).strip())
                    keyword_pills.append(
                        f'<div class="keyword-pill">'
                        f'<span class="keyword-pill-icon">🔍</span>'
                        f'<span>{safe_kw}</span>'
                        f'</div>'
                    )

                keywords_html = (
                    '<div style="padding-bottom: 16px;">'
                    '<div style="max-height: 280px; overflow-y: auto; padding-right: 6px; padding-bottom: 8px; display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;">'
                    + "".join(keyword_pills)
                    + '</div>'
                    '</div>'
                )
                st.markdown(keywords_html, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # STEP 3: Suggested Stock Footage
    # -------------------------------------------------------------------------
    with st.container(key="broll_stock_search_card", border=True):
        c3_head_col1, c3_head_col2 = st.columns([0.78, 0.22])
        with c3_head_col1:
            st.markdown(
                """
                <div class="card-title-group" style="display: flex; align-items: center; min-height: 38px;">
                    <div class="card-step-badge">3</div>
                    <div class="card-title-text">Suggested Stock Footage</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c3_head_col2:
            search_footage_clicked = st.button(
                "Search Footage",
                key="broll_search_footage_btn",
                type="primary",
                use_container_width=True,
            )

        st.markdown(
            """
            <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 14px;">
                Display stock footage suggestions based on AI-generated keywords.
            </p>
            """,
            unsafe_allow_html=True,
        )

        if search_footage_clicked:
            keywords = st.session_state.get("broll_keywords")
            if not keywords:
                st.session_state.broll_stock_error = (
                    "Please generate AI keywords in Step 2 before searching for stock footage."
                )
                st.session_state.broll_stock_results = None
                st.rerun()
            else:
                with st.spinner("Searching Pixabay for stock footage... Please wait."):
                    try:
                        results = search_stock_footage(keywords)
                        for c in results:
                            c["source_type"] = "suggested"
                        st.session_state.broll_stock_results = results
                        st.session_state.broll_stock_video_id = current_video_id
                        st.session_state.broll_stock_error = None
                        st.rerun()
                    except Exception as e:
                        st.session_state.broll_stock_error = str(e)
                        st.rerun()

        stock_err_msg = st.session_state.get("broll_stock_error")
        if stock_err_msg:
            st.markdown(
                f"""
                <div class="status-banner-card error" style="margin-top: 4px; margin-bottom: 12px;">
                    <div class="status-banner-icon error">✕</div>
                    <div>
                        <div class="status-banner-title">Stock footage search failed</div>
                        <div class="status-banner-desc">{html.escape(stock_err_msg)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        stock_results = st.session_state.get("broll_stock_results")

        # Multi-clip selection synchronization
        selected_clips = st.session_state.get("broll_selected_clips")
        if not isinstance(selected_clips, list):
            legacy_clip = st.session_state.get("broll_selected_clip")
            selected_clips = [legacy_clip] if (legacy_clip and isinstance(legacy_clip, dict)) else []
            st.session_state.broll_selected_clips = selected_clips
        else:
            legacy_clip = st.session_state.get("broll_selected_clip")
            if legacy_clip and isinstance(legacy_clip, dict):
                if not any(c.get("id") == legacy_clip.get("id") for c in selected_clips):
                    selected_clips = list(selected_clips) + [legacy_clip]
                    st.session_state.broll_selected_clips = selected_clips

        selected_clip_ids = {c.get("id") for c in selected_clips if isinstance(c, dict) and "id" in c}
        selected_clip = selected_clips[-1] if selected_clips else None
        st.session_state.broll_selected_clip = selected_clip

        if stock_results is None:
            st.markdown(
                """
                <div style="padding-bottom: 16px;">
                    <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 26px 20px; text-align: center;">
                        <div style="font-size: 28px; margin-bottom: 8px;">🎬</div>
                        <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">Footage Gallery Ready</div>
                        <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Search results and clip previews will appear here.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="status-banner-card" style="margin-top: 4px; margin-bottom: 12px; padding: 10px 14px;">
                    <div class="status-banner-icon" style="width: 26px; height: 26px; font-size: 14px;">✓</div>
                    <div>
                        <div class="status-banner-title" style="font-size: 0.84rem;">Stock footage search completed.</div>
                        <div class="status-banner-desc" style="font-size: 0.73rem;">Found {len(stock_results)} relevant video clip{'s' if len(stock_results) != 1 else ''} from Pixabay.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if len(stock_results) == 0:
                st.markdown(
                    """
                    <div style="padding-bottom: 16px;">
                        <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 20px; text-align: center; margin-top: 10px;">
                            <div style="font-size: 0.85rem; color: #9ca3af;">No matching stock footage found for the generated keywords.</div>
                            <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Try generating new keywords or editing the transcript.</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                if total_video_duration <= 0.0:
                    if current_broll_video and Path(current_broll_video).exists():
                        try:
                            meta = get_video_metadata(Path(current_broll_video))
                            total_video_duration = float(meta.get("duration", 0.0) or 0.0)
                        except Exception:
                            pass
                    if total_video_duration <= 0.0 and transcript:
                        ends = [float(s.get("end", 0.0)) for s in transcript if isinstance(s, dict) and "end" in s]
                        if ends:
                            total_video_duration = max(ends)

                # Pre-calculate matching transcript segment for each clip
                clip_matches = [
                    match_clip_to_transcript(c.get("keyword", ""), transcript)
                    for c in stock_results
                ]

                # 1. Master Original Video Timeline Overview
                if total_video_duration > 0.0:
                    master_blocks = []
                    legend_pills = []
                    for idx, (c, m) in enumerate(zip(stock_results, clip_matches)):
                        if m:
                            l_pct, w_pct = calculate_timeline_percentages(
                                m["start"], m["end"], total_video_duration
                            )
                            col = get_segment_color(m["segment_index"])
                            p_range = f"{format_duration(m['start'])} - {format_duration(m['end'])}"
                            clip_id = c.get("id")
                            c_kw = html.escape(c.get("keyword", ""))
                            master_blocks.append(
                                f'<div style="position: absolute; left: {l_pct}%; width: {w_pct}%; height: 100%; '
                                f'background: {col["primary"]}; opacity: 0.88; border-right: 1px solid rgba(255,255,255,0.4); '
                                f'display: flex; align-items: center; justify-content: center; font-size: 0.65rem; color: #ffffff; font-weight: 700;" '
                                f'title="Clip #{clip_id} ({p_range})">#{idx + 1}</div>'
                            )
                            legend_pills.append(
                                f'<span style="background: {col["bg"]}; border: 1px solid {col["border"]}; color: {col["light"]}; '
                                f'font-size: 0.70rem; padding: 2px 8px; border-radius: 4px; font-weight: 600;">'
                                f'#{idx + 1}: {p_range} ({c_kw})</span>'
                            )

                    overview_html = (
                        f'<div style="background: #0d0f17; border: 1px solid #1f2336; border-radius: 12px; padding: 14px 16px; margin-top: 4px; margin-bottom: 16px;">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
                        f'<div style="display: flex; align-items: center; gap: 8px;">'
                        f'<span style="font-size: 0.95rem;">⏱️</span>'
                        f'<span style="font-size: 0.86rem; font-weight: 600; color: #ffffff;">Original Video Timeline & B-roll Placements</span>'
                        f'</div>'
                        f'<span style="font-size: 0.76rem; color: #a78bfa; font-weight: 600; font-family: monospace;">Total Duration: {format_duration(total_video_duration)}</span>'
                        f'</div>'
                        f'<div style="position: relative; width: 100%; height: 22px; background: #161825; border: 1px solid #252a3f; border-radius: 6px; overflow: hidden; margin-bottom: 4px;">'
                        + ("".join(master_blocks) if master_blocks else '<div style="font-size: 0.72rem; color: #8b90a7; text-align: center; line-height: 22px;">No transcript timestamps available for timeline placement</div>')
                        + f'</div>'
                        f'<div style="display: flex; justify-content: space-between; font-size: 0.66rem; color: #6b7280; font-family: monospace; margin-bottom: 8px;">'
                        f'<span>00:00</span>'
                        f'<span>{format_duration(total_video_duration)}</span>'
                        f'</div>'
                        + (f'<div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px;">{"".join(legend_pills)}</div>' if legend_pills else "")
                        + f'</div>'
                    )
                    st.markdown(overview_html, unsafe_allow_html=True)

                # Selected clips summary indicator
                if selected_clips:
                    st.markdown(
                        f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.28); border-radius: 8px; padding: 8px 14px; margin-bottom: 14px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="color: #34d399; font-size: 0.82rem; font-weight: 600;">✓ {len(selected_clips)} footage clip{'s' if len(selected_clips) != 1 else ''} selected for B-roll</span>
                            </div>
                            <span style="font-size: 0.72rem; color: #8b90a7;">Click any selected clip to deselect</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # 2. Stock Footage Gallery with Individual Timeline Placements
                grid_col1, grid_col2 = st.columns(2, gap="medium")
                for idx, clip in enumerate(stock_results):
                    target_col = grid_col1 if (idx % 2 == 0) else grid_col2
                    match = clip_matches[idx]
                    with target_col:
                        is_sel = bool(clip.get("id") in selected_clip_ids)
                        sel_class = " selected" if is_sel else ""
                        sel_badge_html = '<span style="background: #10b981; color: #0b0d14; font-size: 0.7rem; font-weight: 700; padding: 2px 7px; border-radius: 4px; margin-left: 6px;">✓ SELECTED</span>' if is_sel else ""

                        thumb_html = ""
                        if clip.get("thumbnail_url"):
                            safe_thumb = html.escape(clip["thumbnail_url"])
                            thumb_html = (
                                f'<div class="stock-card-thumb-wrap">'
                                f'<img src="{safe_thumb}" alt="Clip thumbnail" loading="lazy" />'
                                f'<span class="stock-badge-res">{html.escape(clip.get("resolution", "HD"))}</span>'
                                f'<span class="stock-badge-duration">{html.escape(clip.get("duration_formatted", "00:00"))}</span>'
                                f'</div>'
                            )

                        safe_tags = html.escape(str(clip.get("tags", "")).strip())
                        safe_kw = html.escape(str(clip.get("keyword", "")).strip())

                        # Build individual visual timeline representation
                        if match and total_video_duration > 0.0:
                            l_pct, w_pct = calculate_timeline_percentages(
                                match["start"], match["end"], total_video_duration
                            )
                            color = get_segment_color(match["segment_index"])
                            p_range = f"{format_duration(match['start'])} - {format_duration(match['end'])}"
                            dur_label = f"{round(match['duration'], 1)}s"
                            snippet = html.escape(
                                match["text"][:75] + ("..." if len(match["text"]) > 75 else "")
                            )

                            timeline_box_html = (
                                f'<div style="background: #0d0f17; border: 1px solid #1a1d2e; border-radius: 8px; padding: 9px 12px; margin-top: 8px; margin-bottom: 10px;">'
                                f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">'
                                f'<span style="font-size: 0.73rem; font-weight: 600; color: {color["light"]};">⏱️ Suggested Placement</span>'
                                f'<span style="font-size: 0.72rem; font-weight: 700; color: #ffffff; font-family: monospace; background: {color["bg"]}; border: 1px solid {color["border"]}; padding: 2px 7px; border-radius: 4px;">{p_range} ({dur_label})</span>'
                                f'</div>'
                                f'<div style="position: relative; width: 100%; height: 8px; background: #161825; border: 1px solid #23273c; border-radius: 4px; overflow: hidden; margin-bottom: 4px;">'
                                f'<div style="position: absolute; left: {l_pct}%; width: {w_pct}%; height: 100%; background: {color["primary"]}; border-radius: 2px;"></div>'
                                f'</div>'
                                f'<div style="display: flex; justify-content: space-between; font-size: 0.65rem; color: #6b7280; font-family: monospace; margin-bottom: 6px;">'
                                f'<span>00:00</span>'
                                f'<span>{format_duration(total_video_duration)}</span>'
                                f'</div>'
                                f'<div style="font-size: 0.71rem; color: #9ca3af; font-style: italic; line-height: 1.3;" title="{html.escape(match["text"])}">'
                                f'"{snippet}"'
                                f'</div>'
                                f'</div>'
                            )
                        else:
                            timeline_box_html = (
                                f'<div style="background: #0d0f17; border: 1px dashed #23273c; border-radius: 8px; padding: 9px 12px; margin-top: 8px; margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">'
                                f'<span style="font-size: 0.75rem; color: #6b7280;">⏱️</span>'
                                f'<span style="font-size: 0.72rem; color: #8b90a7;">Timeline placement: No direct transcript timestamp match</span>'
                                f'</div>'
                            )

                        creator_info = html.escape(str(clip.get("user") or "Pixabay"))
                        suggested_badge_html = '<span style="background: rgba(139, 92, 246, 0.18); border: 1px solid #8b5cf6; color: #c4b5fd; font-size: 0.68rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; margin-left: 6px;">AI SUGGESTED</span>'

                        card_header_html = (
                            f'<div class="stock-card{sel_class}">'
                            f'{thumb_html}'
                            f'<div class="stock-meta-row">'
                            f'<div style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">'
                            f'<span style="font-size: 0.76rem; font-weight: 600; color: #a78bfa;">🔍 #{idx + 1} {safe_kw}</span>'
                            f'{suggested_badge_html}'
                            f'</div>'
                            f'{sel_badge_html}'
                            f'</div>'
                            f'<div style="font-size: 0.70rem; color: #6b7280; margin-bottom: 4px;">👤 Creator: {creator_info} • Pixabay Video #{clip.get("id")}</div>'
                            f'<div class="stock-tags-text" title="{safe_tags}">{safe_tags}</div>'
                            f'{timeline_box_html}'
                            f'</div>'
                        )
                        st.markdown(card_header_html, unsafe_allow_html=True)

                        if clip.get("preview_url"):
                            with st.expander(f"▶ Preview Clip #{clip.get('id')}", expanded=False):
                                st.video(clip["preview_url"])

                        btn_label = "✓ Selected for B-roll" if is_sel else "Select Clip"
                        btn_type = "primary" if is_sel else "secondary"
                        if st.button(
                            btn_label,
                            key=f"broll_select_clip_{clip.get('id')}_{idx}",
                            type=btn_type,
                            use_container_width=True,
                            help="Click to deselect this clip" if is_sel else "Click to select this clip for B-roll",
                        ):
                            current_list = list(st.session_state.get("broll_selected_clips") or [])
                            if is_sel:
                                new_list = [c for c in current_list if c.get("id") != clip.get("id")]
                            else:
                                if not any(c.get("id") == clip.get("id") for c in current_list):
                                    clip_copy = dict(clip)
                                    clip_copy["source_type"] = "suggested"
                                    new_list = current_list + [clip_copy]
                                else:
                                    new_list = current_list

                            st.session_state.broll_selected_clips = new_list
                            st.session_state.broll_selected_clip = new_list[-1] if new_list else None
                            st.session_state.broll_selected_clips_video_id = current_video_id
                            st.rerun()

                        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

                st.markdown("<div style='padding-bottom: 8px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # STEP 4: Manual Stock Footage Search
    # -------------------------------------------------------------------------
    with st.container(key="broll_manual_search_card", border=True):
        c4_head_col1, c4_head_col2 = st.columns([0.78, 0.22])
        with c4_head_col1:
            st.markdown(
                """
                <div class="card-title-group" style="display: flex; align-items: center; min-height: 38px;">
                    <div class="card-step-badge">4</div>
                    <div class="card-title-text">Manual Stock Footage Search</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c4_head_col2:
            st.markdown("<div style='min-height: 38px;'></div>", unsafe_allow_html=True)

        st.markdown(
            """
            <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 14px;">
                Allow users to manually search for and select stock footage independently of AI-generated keywords.
            </p>
            """,
            unsafe_allow_html=True,
        )

        m_search_col1, m_search_col2 = st.columns([0.78, 0.22], gap="small")
        with m_search_col1:
            manual_search_input = st.text_input(
                "Search stock footage query",
                value=st.session_state.get("broll_manual_query", ""),
                placeholder="Enter custom keywords (e.g. coffee shop, nature drone, tech workspace)...",
                label_visibility="collapsed",
                key="broll_manual_search_input",
            )
        with m_search_col2:
            manual_search_clicked = st.button(
                "Search Footage",
                key="broll_manual_search_btn",
                type="primary",
                use_container_width=True,
            )

        if manual_search_clicked:
            clean_m_q = str(manual_search_input or "").strip()
            if not clean_m_q:
                st.session_state.broll_manual_error = "Please enter search keywords before searching for stock footage."
                st.session_state.broll_manual_results = None
                st.rerun()
            else:
                with st.spinner(f"Searching Pixabay for '{clean_m_q}'... Please wait."):
                    try:
                        m_results = search_pixabay_videos(query=clean_m_q, per_page=12)
                        for c in m_results:
                            c["source_type"] = "manual"
                            c["keyword"] = clean_m_q
                        st.session_state.broll_manual_results = m_results
                        st.session_state.broll_manual_query = clean_m_q
                        st.session_state.broll_manual_video_id = current_video_id
                        st.session_state.broll_manual_error = None
                        st.rerun()
                    except Exception as e:
                        st.session_state.broll_manual_error = str(e)
                        st.rerun()

        manual_err_msg = st.session_state.get("broll_manual_error")
        if manual_err_msg:
            st.markdown(
                f"""
                <div class="status-banner-card error" style="margin-top: 4px; margin-bottom: 12px;">
                    <div class="status-banner-icon error">✕</div>
                    <div>
                        <div class="status-banner-title">Manual stock footage search failed</div>
                        <div class="status-banner-desc">{html.escape(manual_err_msg)}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        manual_results = st.session_state.get("broll_manual_results")

        if manual_results is None:
            st.markdown(
                """
                <div style="padding-bottom: 16px;">
                    <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 26px 20px; text-align: center;">
                        <div style="font-size: 28px; margin-bottom: 8px;">🔍</div>
                        <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">Manual Stock Search Ready</div>
                        <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Enter any topic or action above to find custom stock video cutaways.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            q_disp = html.escape(st.session_state.get("broll_manual_query", ""))
            st.markdown(
                f"""
                <div class="status-banner-card" style="margin-top: 4px; margin-bottom: 12px; padding: 10px 14px;">
                    <div class="status-banner-icon" style="width: 26px; height: 26px; font-size: 14px; background: rgba(6, 182, 212, 0.15); color: #06b6d4;">✓</div>
                    <div>
                        <div class="status-banner-title" style="font-size: 0.84rem;">Manual search completed.</div>
                        <div class="status-banner-desc" style="font-size: 0.73rem;">Found {len(manual_results)} video clip{'s' if len(manual_results) != 1 else ''} for "{q_disp}" from Pixabay.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if len(manual_results) == 0:
                st.markdown(
                    f"""
                    <div style="padding-bottom: 16px;">
                        <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 20px; text-align: center; margin-top: 10px;">
                            <div style="font-size: 0.85rem; color: #9ca3af;">No matching stock footage found for "{q_disp}".</div>
                            <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Try searching with different or more general keywords.</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                m_matches = [
                    match_clip_to_transcript(c.get("keyword", ""), transcript)
                    for c in manual_results
                ]

                # Current selected clips
                cur_selected = st.session_state.get("broll_selected_clips") or []
                selected_clip_ids = {c.get("id") for c in cur_selected if isinstance(c, dict) and "id" in c}

                # Gallery
                m_grid_col1, m_grid_col2 = st.columns(2, gap="medium")
                for m_idx, m_clip in enumerate(manual_results):
                    m_target_col = m_grid_col1 if (m_idx % 2 == 0) else m_grid_col2
                    m_match = m_matches[m_idx]
                    with m_target_col:
                        is_sel = bool(m_clip.get("id") in selected_clip_ids)
                        sel_class = " selected" if is_sel else ""
                        sel_badge_html = '<span style="background: #10b981; color: #0b0d14; font-size: 0.7rem; font-weight: 700; padding: 2px 7px; border-radius: 4px; margin-left: 6px;">✓ SELECTED</span>' if is_sel else ""

                        thumb_html = ""
                        if m_clip.get("thumbnail_url"):
                            safe_thumb = html.escape(m_clip["thumbnail_url"])
                            thumb_html = (
                                f'<div class="stock-card-thumb-wrap">'
                                f'<img src="{safe_thumb}" alt="Clip thumbnail" loading="lazy" />'
                                f'<span class="stock-badge-res">{html.escape(m_clip.get("resolution", "HD"))}</span>'
                                f'<span class="stock-badge-duration">{html.escape(m_clip.get("duration_formatted", "00:00"))}</span>'
                                f'</div>'
                            )

                        safe_tags = html.escape(str(m_clip.get("tags", "")).strip())
                        safe_kw = html.escape(str(m_clip.get("keyword", "")).strip())
                        creator_info = html.escape(str(m_clip.get("user") or "Pixabay"))

                        if m_match and total_video_duration > 0.0:
                            l_pct, w_pct = calculate_timeline_percentages(
                                m_match["start"], m_match["end"], total_video_duration
                            )
                            color = get_segment_color(m_match["segment_index"])
                            p_range = f"{format_duration(m_match['start'])} - {format_duration(m_match['end'])}"
                            dur_label = f"{round(m_match['duration'], 1)}s"
                            snippet = html.escape(
                                m_match["text"][:75] + ("..." if len(m_match["text"]) > 75 else "")
                            )
                            timeline_box_html = (
                                f'<div style="background: #0d0f17; border: 1px solid #1a1d2e; border-radius: 8px; padding: 9px 12px; margin-top: 8px; margin-bottom: 10px;">'
                                f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">'
                                f'<span style="font-size: 0.73rem; font-weight: 600; color: {color["light"]};">⏱️ Suggested Placement</span>'
                                f'<span style="font-size: 0.72rem; font-weight: 700; color: #ffffff; font-family: monospace; background: {color["bg"]}; border: 1px solid {color["border"]}; padding: 2px 7px; border-radius: 4px;">{p_range} ({dur_label})</span>'
                                f'</div>'
                                f'<div style="position: relative; width: 100%; height: 8px; background: #161825; border: 1px solid #23273c; border-radius: 4px; overflow: hidden; margin-bottom: 4px;">'
                                f'<div style="position: absolute; left: {l_pct}%; width: {w_pct}%; height: 100%; background: {color["primary"]}; border-radius: 2px;"></div>'
                                f'</div>'
                                f'<div style="display: flex; justify-content: space-between; font-size: 0.65rem; color: #6b7280; font-family: monospace; margin-bottom: 6px;">'
                                f'<span>00:00</span>'
                                f'<span>{format_duration(total_video_duration)}</span>'
                                f'</div>'
                                f'<div style="font-size: 0.71rem; color: #9ca3af; font-style: italic; line-height: 1.3;" title="{html.escape(m_match["text"])}">'
                                f'"{snippet}"'
                                f'</div>'
                                f'</div>'
                            )
                        else:
                            timeline_box_html = (
                                f'<div style="background: #0d0f17; border: 1px dashed #23273c; border-radius: 8px; padding: 9px 12px; margin-top: 8px; margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">'
                                f'<span style="font-size: 0.75rem; color: #06b6d4;">⏱️</span>'
                                f'<span style="font-size: 0.72rem; color: #8b90a7;">Manual Placement: Customize timeline position in Step 5</span>'
                                f'</div>'
                            )

                        manual_badge = '<span style="background: rgba(6, 182, 212, 0.18); border: 1px solid #06b6d4; color: #67e8f9; font-size: 0.68rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; margin-left: 6px;">MANUAL</span>'

                        card_header_html = (
                            f'<div class="stock-card{sel_class}">'
                            f'{thumb_html}'
                            f'<div class="stock-meta-row">'
                            f'<div style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">'
                            f'<span style="font-size: 0.76rem; font-weight: 600; color: #67e8f9;">🔍 #{m_idx + 1} {safe_kw}</span>'
                            f'{manual_badge}'
                            f'</div>'
                            f'{sel_badge_html}'
                            f'</div>'
                            f'<div style="font-size: 0.70rem; color: #6b7280; margin-bottom: 4px;">👤 Creator: {creator_info} • Pixabay Video #{m_clip.get("id")}</div>'
                            f'<div class="stock-tags-text" title="{safe_tags}">{safe_tags}</div>'
                            f'{timeline_box_html}'
                            f'</div>'
                        )
                        st.markdown(card_header_html, unsafe_allow_html=True)

                        if m_clip.get("preview_url"):
                            with st.expander(f"▶ Preview Clip #{m_clip.get('id')}", expanded=False):
                                st.video(m_clip["preview_url"])

                        btn_label = "✓ Selected for B-roll" if is_sel else "Select Clip"
                        btn_type = "primary" if is_sel else "secondary"
                        if st.button(
                            btn_label,
                            key=f"broll_select_manual_clip_{m_clip.get('id')}_{m_idx}",
                            type=btn_type,
                            use_container_width=True,
                            help="Click to deselect this clip" if is_sel else "Click to select this clip for B-roll",
                        ):
                            current_list = list(st.session_state.get("broll_selected_clips") or [])
                            if is_sel:
                                new_list = [c for c in current_list if c.get("id") != m_clip.get("id")]
                            else:
                                if not any(c.get("id") == m_clip.get("id") for c in current_list):
                                    clip_to_add = dict(m_clip)
                                    clip_to_add["source_type"] = "manual"
                                    new_list = current_list + [clip_to_add]
                                else:
                                    new_list = current_list

                            st.session_state.broll_selected_clips = new_list
                            st.session_state.broll_selected_clip = new_list[-1] if new_list else None
                            st.session_state.broll_selected_clips_video_id = current_video_id
                            st.rerun()

                        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

                st.markdown("<div style='padding-bottom: 8px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # STEP 5: B-roll Placement & Timeline
    # Planned: FFmpeg Overlay
    # -------------------------------------------------------------------------
    with st.container(key="broll_placement_card", border=True):
        all_selected = st.session_state.get("broll_selected_clips")
        if not isinstance(all_selected, list) or not all_selected:
            legacy_clip = st.session_state.get("broll_selected_clip")
            all_selected = [legacy_clip] if (legacy_clip and isinstance(legacy_clip, dict)) else []

        c5_head_col1, c5_head_col2 = st.columns([0.76, 0.24])
        with c5_head_col1:
            st.markdown(
                """
                <div class="card-title-group" style="display: flex; align-items: center; min-height: 38px;">
                    <div class="card-step-badge">5</div>
                    <div class="card-title-text">B-roll Placement & Timeline</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c5_head_col2:
            generate_video_clicked = st.button(
                "Generate Video",
                key="broll_generate_video_btn",
                type="primary",
                use_container_width=True,
                disabled=bool(
                    not all_selected
                    or not current_broll_video
                    or st.session_state.get("broll_is_generating", False)
                ),
            )

        st.markdown(
            """
            <p style="font-size: 0.82rem; color: #8b90a7; margin-top: 4px; margin-bottom: 14px;">
                Review selected stock footage and position cutaways on the video timeline before generating your final video.
            </p>
            """,
            unsafe_allow_html=True,
        )

        gen_error = st.session_state.get("broll_generation_error")
        if gen_error:
            safe_err = html.escape(str(gen_error))
            st.markdown(
                f"""
                <div class="status-banner-card" style="margin-top: 4px; margin-bottom: 12px; padding: 10px 14px; border-left: 4px solid #ef4444;">
                    <div class="status-banner-icon" style="background: rgba(239, 68, 68, 0.15); color: #ef4444; width: 26px; height: 26px; font-size: 14px;">✕</div>
                    <div>
                        <div class="status-banner-title" style="color: #ef4444; font-size: 0.84rem;">Video Generation Error</div>
                        <div class="status-banner-desc" style="font-size: 0.73rem;">{safe_err}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if not all_selected:
            st.markdown(
                """
                <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 26px 20px; text-align: center; margin-top: 6px; margin-bottom: 10px;">
                    <div style="font-size: 28px; margin-bottom: 8px;">⏱️</div>
                    <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">No Stock Footage Selected</div>
                    <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Click <b>Select Clip</b> in Step 3 (Suggested Stock Footage) or Step 4 (Manual Stock Footage Search) to review and configure its B-roll timeline placement.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            default_placements = calculate_clip_placements(all_selected, transcript, total_video_duration)
            for p in default_placements:
                c = p["clip"]
                c_id = c.get("id") or "clip"
                start_state_key = f"broll_time_start_{c_id}"
                end_state_key = f"broll_time_end_{c_id}"
                if start_state_key not in st.session_state:
                    st.session_state[start_state_key] = float(p["start"])
                if end_state_key not in st.session_state:
                    st.session_state[end_state_key] = float(p["end"])

            # -------------------------------------------------------------
            # Master Timeline Overview
            # -------------------------------------------------------------
            if total_video_duration > 0:
                if len(all_selected) == 1:
                    p = default_placements[0]
                    c = p["clip"]
                    clip_id = c.get("id") or "clip"
                    start_state_key = f"broll_time_start_{clip_id}"
                    end_state_key = f"broll_time_end_{clip_id}"
                    col_scheme = get_segment_color(p.get("segment_index", 0))
                    l_pct, w_pct = calculate_timeline_percentages(
                        st.session_state[start_state_key],
                        st.session_state[end_state_key],
                        total_video_duration,
                    )
                    start_str = format_duration(st.session_state[start_state_key])
                    end_str = format_duration(st.session_state[end_state_key])
                    total_str = format_duration(total_video_duration)
                    p_range_str = f"{start_str} - {end_str}"
                    placement_duration = max(0.0, float(st.session_state[end_state_key]) - float(st.session_state[start_state_key]))
                    timeline_preview_html = (
                        f'<div style="background: #0d0f17; border: 1px solid #1f2336; border-radius: 10px; padding: 12px 14px; margin-top: 10px; margin-bottom: 12px;">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">'
                        f'<span style="font-size: 0.78rem; font-weight: 600; color: #ffffff;">Proposed Timeline Placement</span>'
                        f'<span style="font-size: 0.72rem; color: {col_scheme["light"]}; font-family: monospace; font-weight: 600;">{p_range_str} ({placement_duration:.1f}s)</span>'
                        f'</div>'
                        f'<div style="position: relative; width: 100%; height: 18px; background: #161825; border: 1px solid #252a3f; border-radius: 6px; overflow: hidden; margin-bottom: 4px;">'
                        f'<div style="position: absolute; left: {l_pct}%; width: {w_pct}%; height: 100%; background: {col_scheme["primary"]}; opacity: 0.90; '
                        f'display: flex; align-items: center; justify-content: center; font-size: 0.65rem; color: #ffffff; font-weight: 700;">'
                        f'Clip #{clip_id}</div>'
                        f'</div>'
                        f'<div style="display: flex; justify-content: space-between; font-size: 0.65rem; color: #6b7280; font-family: monospace;">'
                        f'<span>00:00</span>'
                        f'<span>{total_str}</span>'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(timeline_preview_html, unsafe_allow_html=True)
                else:
                    timeline_blocks = []
                    legend_items = []
                    for p_idx, p in enumerate(default_placements):
                        c = p["clip"]
                        c_id = c.get("id") or "clip"
                        s_val = float(st.session_state.get(f"broll_time_start_{c_id}", p["start"]))
                        e_val = float(st.session_state.get(f"broll_time_end_{c_id}", p["end"]))
                        l_pct, w_pct = calculate_timeline_percentages(s_val, e_val, total_video_duration)
                        col_scheme = get_segment_color(p.get("segment_index", p_idx))
                        p_dur = max(0.0, e_val - s_val)
                        is_manual = (c.get("source_type") == "manual")
                        type_tag = "[MANUAL]" if is_manual else "[SUGGESTED]"
                        timeline_blocks.append(
                            f'<div style="position: absolute; left: {l_pct}%; width: {w_pct}%; height: 100%; '
                            f'background: {col_scheme["primary"]}; opacity: 0.90; display: flex; align-items: center; '
                            f'justify-content: center; font-size: 0.65rem; color: #ffffff; font-weight: 700; white-space: nowrap; overflow: hidden;">'
                            f'Clip #{c_id}</div>'
                        )
                        legend_items.append(
                            f'<span style="background: {col_scheme["bg"]}; border: 1px solid {col_scheme["border"]}; color: {col_scheme["light"]}; '
                            f'padding: 2px 7px; border-radius: 4px; font-size: 0.68rem; font-family: monospace; font-weight: 600;">'
                            f'{type_tag} Clip #{c_id}: {format_duration(s_val)} - {format_duration(e_val)} ({p_dur:.1f}s)</span>'
                        )
                    blocks_html = "".join(timeline_blocks)
                    legend_html = "".join(legend_items)
                    total_str = format_duration(total_video_duration)

                    suggested_count = sum(1 for c in all_selected if c.get("source_type") != "manual")
                    manual_count = sum(1 for c in all_selected if c.get("source_type") == "manual")
                    if manual_count > 0 and suggested_count > 0:
                        status_detail = f"✓ {len(all_selected)} Clips Scheduled ({suggested_count} Suggested, {manual_count} Manual)"
                    elif manual_count > 0:
                        status_detail = f"✓ {len(all_selected)} Clips Scheduled ({manual_count} Manual)"
                    else:
                        status_detail = f"✓ {len(all_selected)} Clips Scheduled"

                    timeline_preview_html = (
                        f'<div style="background: #0d0f17; border: 1px solid #1f2336; border-radius: 10px; padding: 12px 14px; margin-top: 10px; margin-bottom: 12px;">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">'
                        f'<span style="font-size: 0.78rem; font-weight: 600; color: #ffffff;">Proposed Timeline Placement</span>'
                        f'<span style="font-size: 0.72rem; color: #34d399; font-family: monospace; font-weight: 600;">{status_detail}</span>'
                        f'</div>'
                        f'<div style="position: relative; width: 100%; height: 20px; background: #161825; border: 1px solid #252a3f; border-radius: 6px; overflow: hidden; margin-bottom: 6px;">'
                        f'{blocks_html}'
                        f'</div>'
                        f'<div style="display: flex; justify-content: space-between; font-size: 0.65rem; color: #6b7280; font-family: monospace; margin-bottom: 8px;">'
                        f'<span>00:00</span>'
                        f'<span>{total_str}</span>'
                        f'</div>'
                        f'<div style="display: flex; flex-wrap: wrap; gap: 6px;">'
                        f'{legend_html}'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(timeline_preview_html, unsafe_allow_html=True)

            # -------------------------------------------------------------
            # Per-Clip Placement Configuration Cards
            # -------------------------------------------------------------
            max_upper = max(total_video_duration, 3600.0) if total_video_duration > 0 else 3600.0

            for p_idx, p in enumerate(default_placements):
                c = p["clip"]
                clip_id = c.get("id") or "clip"
                clip_kw = str(c.get("keyword", "")).strip()
                clip_dur = float(c.get("duration", 0.0) or 0.0)
                clip_res = c.get("resolution", "HD")
                clip_thumb = c.get("thumbnail_url", "")
                clip_tags = c.get("tags", "")

                match = p.get("match")
                seg_idx = p.get("segment_index", 0)
                seg_text = p.get("text", "")
                col_scheme = get_segment_color(seg_idx)

                start_state_key = f"broll_time_start_{clip_id}"
                end_state_key = f"broll_time_end_{clip_id}"

                if len(all_selected) > 1:
                    st.markdown(
                        f"""
                        <div style="font-size: 0.80rem; font-weight: 600; color: #a78bfa; margin-top: 14px; margin-bottom: 6px;">
                            Clip {p_idx + 1} of {len(all_selected)}: <span style="color: #ffffff;">{html.escape(clip_kw or str(clip_id))}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                rev_col1, rev_col2 = st.columns([0.42, 0.58], gap="medium")

                with rev_col1:
                    thumb_markup = ""
                    if clip_thumb:
                        safe_thumb_url = html.escape(clip_thumb)
                        safe_res_label = html.escape(clip_res)
                        safe_dur_label = html.escape(format_duration(clip_dur))
                        thumb_markup = (
                            f'<div class="stock-card-thumb-wrap" style="height: 140px; margin-bottom: 8px;">'
                            f'<img src="{safe_thumb_url}" alt="Selected Clip" style="width: 100%; height: 100%; object-fit: cover; border-radius: 6px;" />'
                            f'<span class="stock-badge-res">{safe_res_label}</span>'
                            f'<span class="stock-badge-duration">{safe_dur_label}</span>'
                            f'</div>'
                        )
                    safe_kw = html.escape(clip_kw)
                    safe_tags = html.escape(str(clip_tags))

                    is_manual = (c.get("source_type") == "manual")
                    source_badge = (
                        '<span style="background: rgba(6, 182, 212, 0.18); border: 1px solid #06b6d4; color: #67e8f9; font-size: 0.68rem; font-weight: 700; padding: 2px 6px; border-radius: 4px;">MANUAL</span>'
                        if is_manual
                        else '<span style="background: rgba(139, 92, 246, 0.18); border: 1px solid #8b5cf6; color: #c4b5fd; font-size: 0.68rem; font-weight: 700; padding: 2px 6px; border-radius: 4px;">AI SUGGESTED</span>'
                    )
                    creator_info = html.escape(str(c.get("user") or "Pixabay"))

                    st.markdown(
                        f"""
                        <div style="background: #0d0f17; border: 1px solid #1f2336; border-radius: 10px; padding: 12px 14px;">
                            {thumb_markup}
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
                                    <span style="font-size: 0.82rem; font-weight: 600; color: #a78bfa;">🔍 {safe_kw}</span>
                                    {source_badge}
                                </div>
                                <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #34d399; font-size: 0.68rem; font-weight: 700; padding: 2px 6px; border-radius: 4px;">SELECTED</span>
                            </div>
                            <div style="font-size: 0.70rem; color: #6b7280; margin-bottom: 2px;">👤 Creator: {creator_info} • Pixabay Video #{clip_id}</div>
                            <div style="font-size: 0.72rem; color: #8b90a7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{safe_tags}">{safe_tags}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if c.get("preview_url"):
                        with st.expander(f"▶ Preview Clip #{clip_id}", expanded=False):
                            st.video(c["preview_url"])

                    remove_btn_label = "✕ Change / Remove Selection" if len(all_selected) == 1 else f"✕ Remove Clip #{clip_id}"
                    if st.button(remove_btn_label, key=f"broll_remove_selected_clip_btn_{clip_id}", use_container_width=True):
                        new_sel = [x for x in all_selected if x.get("id") != c.get("id")]
                        st.session_state.broll_selected_clips = new_sel
                        st.session_state.broll_selected_clip = new_sel[-1] if new_sel else None
                        st.session_state.broll_selected_clips_video_id = current_video_id if new_sel else None
                        st.session_state.broll_generation_error = None
                        st.rerun()

                with rev_col2:
                    safe_seg_text = html.escape(str(seg_text))
                    if match:
                        seg_badge = f"Segment #{seg_idx + 1}"
                        context_body = f'"{safe_seg_text}"'
                    elif is_manual:
                        seg_badge = "Manual Placement"
                        context_body = "Custom stock footage selected via manual search. Position clip along the timeline using timestamps below."
                    else:
                        seg_badge = "Custom Placement"
                        context_body = "Suggested footage with custom timeline positioning. Adjust timestamps below."

                    st.markdown(
                        f"""
                        <div style="background: #0d0f17; border: 1px solid #1f2336; border-radius: 10px; padding: 12px 14px; margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                <span style="font-size: 0.78rem; font-weight: 600; color: #ffffff;">Target Transcript Context</span>
                                <span style="background: {col_scheme['bg']}; border: 1px solid {col_scheme['border']}; color: {col_scheme['light']}; font-size: 0.68rem; padding: 2px 7px; border-radius: 4px; font-weight: 600;">{seg_badge}</span>
                            </div>
                            <div style="font-size: 0.77rem; color: #d1d5db; font-style: italic; line-height: 1.35; background: #12141e; border: 1px solid #1e2235; border-radius: 6px; padding: 8px 10px;">
                                {context_body}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    curr_start_val = float(st.session_state.get(start_state_key, p["start"]))
                    curr_end_val = float(st.session_state.get(end_state_key, p["end"]))

                    input_col_a, input_col_b = st.columns(2)
                    with input_col_a:
                        new_start = st.number_input(
                            "Start Timestamp (seconds)",
                            min_value=0.0,
                            max_value=max(0.0, max_upper - 0.1),
                            value=float(min(curr_start_val, max_upper - 0.1)),
                            step=0.5,
                            format="%.2f",
                            key=f"broll_num_start_{clip_id}",
                        )
                    with input_col_b:
                        new_end = st.number_input(
                            "End Timestamp (seconds)",
                            min_value=0.1,
                            max_value=max_upper,
                            value=float(min(max(curr_end_val, 0.1), max_upper)),
                            step=0.5,
                            format="%.2f",
                            key=f"broll_num_end_{clip_id}",
                        )

                    st.session_state[start_state_key] = new_start
                    st.session_state[end_state_key] = new_end

                    placement_duration = max(0.0, new_end - new_start)
                    if new_start >= new_end:
                        st.warning("⚠️ Start timestamp must be strictly before End timestamp.")
                    else:
                        start_str = format_duration(new_start)
                        end_str = format_duration(new_end)
                        st.markdown(
                            f"""
                            <div style="display: flex; justify-content: space-between; font-size: 0.76rem; color: #a78bfa; font-family: monospace; padding: 4px 2px;">
                                <span>⏱️ Placement: {start_str} → {end_str}</span>
                                <span>Duration: {placement_duration:.1f}s</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

            # -------------------------------------------------------------
            # Generation Execution
            # -------------------------------------------------------------
            if generate_video_clicked:
                invalid_timestamps = False
                for c in all_selected:
                    c_id = c.get("id") or "clip"
                    st_val = float(st.session_state.get(f"broll_time_start_{c_id}", 0.0))
                    en_val = float(st.session_state.get(f"broll_time_end_{c_id}", 0.0))
                    if st_val >= en_val:
                        invalid_timestamps = True
                        break

                if invalid_timestamps:
                    st.session_state.broll_generation_error = "Start timestamp must be strictly before End timestamp."
                    st.rerun()

                if not current_broll_video or not Path(current_broll_video).exists():
                    st.session_state.broll_generation_error = "Target input video is missing or invalid. Please upload or select a video."
                    st.rerun()

                st.session_state.broll_is_generating = True
                st.session_state.broll_generation_error = None

                if st.session_state.get("app_state") == AppState.IDLE:
                    set_state(AppState.UPLOADED)
                set_state(AppState.PROCESSING)

                progress_bar = st.progress(0.0)
                status_box = st.empty()

                def update_gen_progress(ratio: float, msg: str):
                    progress_bar.progress(min(max(0.0, float(ratio)), 1.0))
                    safe_msg = html.escape(msg)
                    status_box.markdown(
                        f"""
                        <div style="font-size: 0.80rem; color: #a78bfa; font-weight: 500; margin-top: 4px;">
                            ⏳ {safe_msg}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                try:
                    out_filename = generate_safe_filename(f"broll_{Path(current_broll_video).stem}.mp4")
                    output_file_path = temp_dir / out_filename
                    placements_payload = []
                    for c in all_selected:
                        c_id = c.get("id") or "clip"
                        st_key = f"broll_time_start_{c_id}"
                        en_key = f"broll_time_end_{c_id}"
                        s_val = float(st.session_state.get(st_key, 0.0))
                        e_val = float(st.session_state.get(en_key, 0.0))
                        if s_val < e_val:
                            placements_payload.append({
                                "clip": c,
                                "start": s_val,
                                "end": e_val,
                            })

                    if not placements_payload:
                        raise ValueError("No valid placements configured for generation.")

                    rendered_output = compose_broll_video(
                        original_video_path=Path(current_broll_video),
                        broll_placements=placements_payload,
                        output_path=output_file_path,
                        temp_dir=temp_dir,
                        progress_callback=update_gen_progress,
                    )

                    st.session_state.processed_video = str(rendered_output)
                    st.session_state.video_metadata = get_video_metadata(rendered_output)
                    st.session_state.broll_generation_success = True
                    st.session_state.broll_generation_error = None
                    st.session_state.broll_is_generating = False

                    if "temp_files" not in st.session_state or not isinstance(st.session_state.temp_files, list):
                        st.session_state.temp_files = []
                    st.session_state.temp_files.append(str(rendered_output))

                    set_state(AppState.COMPLETED)
                    st.session_state.current_page = "export"
                    st.rerun()

                except Exception as e:
                    st.session_state.broll_generation_error = str(e)
                    st.session_state.broll_is_generating = False
                    set_state(AppState.FAILED)
                    st.rerun()
