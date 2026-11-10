# AI Video Editor

An AI-powered video editing application built with Python and Streamlit. It allows users to upload videos, apply AI-based background effects, preview the processed output, and download the edited video.

## Features

### Background Editing
- **Background Blur:** Apply blur effects to the background while keeping the foreground subject intact.
- **White Background:** Replace the existing background with a solid white background.
- **Background Replacement:** Replace the original background with a custom image.
- **Adjustable Blur Strength:** Choose between Light, Medium, and Strong blur levels.

### Video Processing
- Upload and process individual videos.
- AI-powered person segmentation using MediaPipe.
- Video processing using OpenCV.
- Audio preservation using FFmpeg.
- Preview the original and processed videos.
- Download the final processed video.

### Planned Features
- AI-assisted video transcription.
- Automatic B-roll keyword generation.
- Stock footage search using Pixabay/Pexels.
- Timestamp-based B-roll placement.
- AI-assisted video editing workflow.

> Note: Planned features are not necessarily available in the current application.

---

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

---

## Getting Started

Follow these instructions to download and run the application locally.

### 1. Prerequisites

Make sure you have the following installed:

- Python 3.12 (recommended compatibility target; verify against the project's current dependency versions).
- Git
- pip

### 2. Clone the Repository

Open your terminal or PowerShell and execute:

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
```

Navigate into the cloned repository:

```bash
cd videoediting
```

Replace `videoediting` with the actual repository directory name if different.

### 3. Create a Virtual Environment

Create a Python virtual environment:

```bash
py -3.12 -m venv .venv
```

### 4. Activate the Virtual Environment

For Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

For Windows Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

For macOS/Linux:

```bash
source .venv/bin/activate
```

Once activated, your terminal should display:

```text
(.venv)
```

### 5. Upgrade pip

```bash
python -m pip install --upgrade pip
```

### 6. Install Dependencies

Install all required Python packages:

```bash
pip install -r requirements.txt
```

This installs the dependencies specified by the project.

### 7. Run the Application

Start the Streamlit application:

```bash
streamlit run app/main.py
```

Once the application starts, Streamlit will provide a local URL.

Open the following address in your browser:

```text
http://localhost:8501
```

---

## Project Structure

The application follows a modular architecture.

```text
videoediting/
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
│       └── state.py
│
├── core/
│   ├── video_io.py
│   ├── worker.py
│   ├── audio.py
│   └── utils.py
│
├── temp/
│
├── requirements.txt
├── README.md
└── .gitignore
```

*The structure above is illustrative. Refer to the actual repository for the latest files and directories.*

---

## How to Use

1. Launch the application.
2. Navigate to the Editor workspace.
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

---

## Troubleshooting

### MediaPipe Installation Issues

If MediaPipe installation fails:

1. Verify your Python version.
2. Check whether the MediaPipe version specified in `requirements.txt` supports your Python version and operating system.
3. Upgrade pip:

```bash
python -m pip install --upgrade pip
```

4. Reinstall the dependencies:

```bash
pip install -r requirements.txt
```

### Streamlit Command Not Found

Make sure your virtual environment is activated.
