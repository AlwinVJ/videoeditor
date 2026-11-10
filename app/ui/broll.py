from pathlib import Path
import streamlit as st


def render_broll_page():
    """
    Render the dedicated AI B-roll & Stock Footage workspace.
    Provides a modular, extensible structure for the planned tutorial features:
    1. Video Transcription (Groq Whisper)
    2. AI Keyword Generation (Groq LLM)
    3. Stock Footage Search (Pixabay/Pexels)
    4. B-roll Placement (Timeline positioning)
    5. B-roll Preview
    All sections feature clean logical empty states and clear status badges.
    """
    st.markdown(
        """
        <div class="page-header-container">
            <div class="header-icon-box" style="color: #7c5cfc;">
                ✨
            </div>
            <div>
                <div class="header-text-title">AI B-roll & Stock Footage</div>
                <div class="header-text-desc">Transcribe your video, generate stock footage keywords, and insert relevant B-roll clips.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Check whether an input video is currently loaded
    input_video_path = st.session_state.get("input_video_path")
    has_video = input_video_path and Path(input_video_path).exists()

    if not has_video:
        st.info("💡 To use AI B-roll tools, please first upload a video in the Editor tab.")

    # Two column layout for B-roll workspace
    col_left, col_right = st.columns([0.48, 0.52], gap="large")

    with col_left:
        # SECTION 1: Video Transcription
        st.markdown(
            """
            <div class="editor-card">
                <div class="editor-card-header">
                    <div class="card-title-group">
                        <div class="card-step-badge">1</div>
                        <div class="card-title-text">Video Transcription</div>
                    </div>
                    <span style="font-size: 0.72rem; padding: 3px 8px; border-radius: 6px; background: rgba(124, 92, 252, 0.15); color: #a78bfa; border: 1px solid rgba(124, 92, 252, 0.3);">Planned: Groq Whisper</span>
                </div>
                <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 12px;">
                    Extract audio and generate timestamped transcript segments for accurate B-roll matching.
                </p>
                <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 24px; text-align: center;">
                    <div style="font-size: 28px; margin-bottom: 8px;">🎙️</div>
                    <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">Transcript Workspace Ready</div>
                    <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Segment-level navigation and timestamp sync will appear here.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # SECTION 2: AI Keyword Generation
        st.markdown(
            """
            <div class="editor-card">
                <div class="editor-card-header">
                    <div class="card-title-group">
                        <div class="card-step-badge">2</div>
                        <div class="card-title-text">AI Keyword Generation</div>
                    </div>
                    <span style="font-size: 0.72rem; padding: 3px 8px; border-radius: 6px; background: rgba(124, 92, 252, 0.15); color: #a78bfa; border: 1px solid rgba(124, 92, 252, 0.3);">Planned: Groq LLM</span>
                </div>
                <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 12px;">
                    Generate context-aware visual search queries and footage suggestions for each transcript segment.
                </p>
                <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 24px; text-align: center;">
                    <div style="font-size: 28px; margin-bottom: 8px;">🧠</div>
                    <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">AI Suggestions Ready</div>
                    <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Automated keyword pills and custom search inputs will populate here.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_right:
        # SECTION 3: Stock Footage Search
        st.markdown(
            """
            <div class="editor-card">
                <div class="editor-card-header">
                    <div class="card-title-group">
                        <div class="card-step-badge">3</div>
                        <div class="card-title-text">Stock Footage Search</div>
                    </div>
                    <span style="font-size: 0.72rem; padding: 3px 8px; border-radius: 6px; background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3);">Pixabay / Pexels</span>
                </div>
                <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 12px;">
                    Search free video repositories and select high-resolution B-roll clips.
                </p>
                <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 24px; text-align: center;">
                    <div style="font-size: 28px; margin-bottom: 8px;">🎬</div>
                    <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">Footage Gallery Ready</div>
                    <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Thumbnail search grid and clip duration selectors will appear here.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # SECTION 4 & 5: Placement & Timeline Preview
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
                <p style="font-size: 0.82rem; color: #8b90a7; margin-bottom: 12px;">
                    Position selected stock clips at specific start, middle, or end timestamps.
                </p>
                <div style="background: #10121c; border: 1px dashed #282d44; border-radius: 10px; padding: 24px; text-align: center;">
                    <div style="font-size: 28px; margin-bottom: 8px;">⏱️</div>
                    <div style="font-size: 0.88rem; font-weight: 500; color: #d1d5db;">Timeline Editor Ready</div>
                    <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Multi-track visual timeline and overlay preview will render here.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
