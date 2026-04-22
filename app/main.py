import streamlit as st
from pathlib import Path
import uuid

#Path configuration
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Video Background Editor", layout="wide")


# Save uploaded file with a unique name to avoid overwriting
def save_uploaded_file(uploaded_file):
    unique_name = f"{uuid.uuid4()}_{uploaded_file.name}"
    file_path = TEMP_DIR / unique_name

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return file_path

# Return correct MIME type (fallback if missing).
def get_mime_type(uploaded_file):
    return uploaded_file.type if uploaded_file.type else "application/octet-stream"


# UI
st.title("🎬 Video Background Editor")

uploaded_file = st.file_uploader(
    "Upload a video",
    type=["mp4", "mov", "avi"]
)

if uploaded_file:
    st.subheader("Preview")
    st.video(uploaded_file)

    # Save file
    file_path = save_uploaded_file(uploaded_file)
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
        st.download_button(
            label="Download Uploaded Video",
            data=f,
            file_name=uploaded_file.name,
            mime=mime_type
        )