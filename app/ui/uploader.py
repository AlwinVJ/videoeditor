from pathlib import Path
import streamlit as st
import cv2
import numpy as np

from core.utils import generate_safe_filename


def save_uploaded_file(
    uploaded_file,
    temp_dir: Path
):

    safe_name = generate_safe_filename(
        uploaded_file.name
    )

    file_path = temp_dir / safe_name

    with open(file_path, "wb") as f:
        f.write(
            uploaded_file.getbuffer()
        )

    return file_path


def render_video_uploader():

    uploaded_file = st.file_uploader(
        "Upload a video",
        type=["mp4", "mov", "avi"],
        key=st.session_state.uploader_key
    )

    return uploaded_file


def render_background_uploader():

    uploaded_bg = st.file_uploader(
        "Upload Background Image",
        type=["jpg", "png"]
    )

    bg_image = None

    if uploaded_bg:

        file_bytes = np.asarray(
            bytearray(
                uploaded_bg.read()
            ),
            dtype=np.uint8
        )

        bg_image = cv2.imdecode(
            file_bytes,
            cv2.IMREAD_COLOR
        )

    return uploaded_bg, bg_image