# AI Video Editor

An AI-powered video editing application built with Python and Streamlit. It allows users to upload videos, apply AI-based background effects, preview processed output, and download edited videos.

## Live Demo

**Try the application:** [AI Video Editor](https://videoeditor-bg.streamlit.app/)

## Features

### 1. Background Editing

- **Background Blur:** Apply blur effects to the background while keeping the foreground subject intact.
- **White Background:** Replace the existing background with a solid white background.
- **Background Replacement:** Replace the original background with a custom image.
- **Adjustable Blur Strength:** Choose between Light, Medium, and Strong blur levels.

### 2. Video Processing

- Upload and process individual videos.
- AI-powered person segmentation using MediaPipe.
- Frame processing using OpenCV.
- Audio preservation using FFmpeg.
- Preview original and processed videos.
- Download the final processed video.

### 3. AI B-roll Editor

The application also includes an AI B-roll editing workspace for developing an automated video editing workflow.

Planned capabilities include:

- AI-assisted video transcription.
- Automatic B-roll keyword generation.
- Stock footage search using Pixabay/Pexels.
- Timestamp-based B-roll placement.
- AI-assisted video editing workflow.

> **Note:** B-roll capabilities are under development. Individual features may not yet be fully functional or available in the live application.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Streamlit | Application interface |
| OpenCV | Video processing |
| MediaPipe | AI-based person segmentation |
| NumPy | Image and frame manipulation |
| FFmpeg | Video encoding and audio processing |
| imageio-ffmpeg | FFmpeg binary integration |

## Project Structure

The application follows a modular architecture.

```text
videoeditor/
│
├── app/
│   ├── main.py
│   └── ui/
│       ├── sidebar.py
│       ├── editor.py
│       ├── uploader.py
│       ├── controls.py
│       ├── processing.py
│       ├── preview.py
│       ├── state.py
│       └── broll.py
│
├── core/
│   ├── video_io.py
│   ├── worker.py
│   ├── audio.py
│   ├── utils.py
│   └── transcription.py
│
├── temp/
│
├── requirements.txt
├── README.md
└── .gitignore
```

*The structure above is illustrative. Refer to the repository for the latest files and directories.*

## How to Use

1. Open the [AI Video Editor web application](https://videoeditor-bg.streamlit.app/).
2. Navigate to the **Editor** workspace.
3. Upload a video.
4. Select the desired background effect:
   - Blur Background
   - White Background
   - Replace Background
5. Configure the blur strength or upload a replacement background image.
6. Click **Process Video**.
7. Wait for processing to complete.
8. Preview the processed video.
9. Download the final output.

## Troubleshooting

### Video Processing Issues

- Ensure the uploaded video uses a supported format.
- Check that the video file is not corrupted.
- Try uploading a smaller video if processing takes too long.

### MediaPipe Issues

MediaPipe compatibility depends on the Python version, operating system, and installed package version. Refer to the project's dependency configuration when investigating compatibility issues.

---

**Built with Python, Streamlit, OpenCV, MediaPipe, and FFmpeg.**
