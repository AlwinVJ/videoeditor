# AI Video Background Editor

## Overview

This project is an AI-powered video editing application that performs real-time background segmentation and applies visual effects such as blur, background replacement, and white background while preserving the original audio.

## Features

* Human background segmentation using MediaPipe
* Effects: Blur, White Background, Background Replacement
* Audio preservation using FFmpeg (no system dependency)
* Optimized processing (frame scaling + skipping)
* Live preview and download via Streamlit UI

## Architecture

1. Upload video
2. Extract frames using OpenCV
3. Apply segmentation mask
4. Apply selected effect
5. Generate processed video (no audio)
6. Merge original audio using FFmpeg
7. Display and download output

## Tech Stack

* Python
* OpenCV
* MediaPipe
* NumPy
* Streamlit
* imageio-ffmpeg

## Run Locally

```bash
uv pip install -r requirements.txt
uv run streamlit run app/main.py
```

## Deployment

Deployed on Streamlit Cloud (no system dependencies required)

## 📌 Future Improvements

* Real-time video processing
* GPU acceleration
* Background video replacement
* Multi-person segmentation
