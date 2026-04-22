import sys
from pathlib import Path

# To import other manually packages from the project (optional)
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import streamlit as st
import uuid
from core.utils import generate_safe_filename, clear_specific_files

#Path configuration
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Video Background Editor", layout="wide")

# Session state initialization
if "temp_files" not in st.session_state:
    st.session_state.temp_files = []

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = "uploaded_video"


# Save uploaded file with a unique name to avoid overwriting
def save_uploaded_file(uploaded_file):
    safe_name = generate_safe_filename(uploaded_file.name)
    file_path = TEMP_DIR / safe_name

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return file_path

# Return correct MIME type (fallback if missing).
def get_mime_type(uploaded_file):
    return uploaded_file.type if uploaded_file.type else "application/octet-stream"

# Clear temp files + reset UI + session state
def reset_and_clear_all():

    # Delete files from disk
    clear_specific_files(st.session_state.temp_files)

    # Reset tracked files
    st.session_state.temp_files = []

    # Clear uploaded file (UI state)
    # if "uploaded_video" in st.session_state:
    #     st.session_state.pop("Uploaded_video", None)
    
    # st.session_state.clear()
    
    st.session_state.uploader_key = str(uuid.uuid4())
    st.success("All files cleared and reset successfully!")
    
    
    # Force UI refresh
    st.rerun()




# UI
st.title("🎬 Video Background Editor")

if st.button("Reset and Clear All"):
    reset_and_clear_all()

uploaded_file = st.file_uploader(
    "Upload a video",
    type=["mp4", "mov", "avi"],
    key=st.session_state.uploader_key
)

if uploaded_file:
    st.subheader("Preview")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.video(uploaded_file, width=500)

    # Save file
    file_path = save_uploaded_file(uploaded_file)
    # Track file
    if file_path not in st.session_state.temp_files:
        st.session_state.temp_files.append(file_path)
    
    st.success(f"File saved: {file_path.name}")

    # Future-ready UI
    effect = st.selectbox(
        "Select Effect",
        ["None", "Blur Background", "Replace Background"]
    )

    process_btn = st.button("Process Video")

    # Download section
    st.subheader("Download (Test)")

    mime_type = get_mime_type(uploaded_file)

    with open(file_path, "rb") as f:
        video_bytes = file_path.read_bytes()
    st.download_button(
        label="Download Uploaded Video",
        data=video_bytes,
        file_name=uploaded_file.name,
        mime=mime_type
    )
    
    st.subheader("Clear the uploaded files")

