import cv2
import shutil
from pathlib import Path
from core.segmentation import apply_background_effect
from core.audio import merge_audio


def process_video(input_path: Path, output_path: Path, effect="blur", bg_image=None, progress_callback=None):
    # Open video
    cap = cv2.VideoCapture(str(input_path))

    if not cap.isOpened():
        raise ValueError("Error opening video file")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps > 0 else 24

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    temp_output = output_path.parent / f"temp_{output_path.name}"


    # Define codec and output
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(temp_output), fourcc, fps, (width, height))

    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Apply segmentation-based effect
        processed_frame = apply_background_effect(
            frame,
            effect=effect,
            bg_image=bg_image
        )

        out.write(processed_frame)

        if progress_callback and total_frames > 0:
            if frame_count % 5 == 0 or frame_count == total_frames:
                progress_callback(min(frame_count / total_frames, 1.0))

        # Optional debug (remove later)
        if frame_count % 30 == 0:
            print(f"Processed {frame_count} frames")

    # Release resources
    cap.release()
    out.release()
    
    # Merge Audio
    try:
        merge_audio(input_path, temp_output, output_path)
    except Exception as e:
        print("Audio merge failed, using video without audio:", e)
        shutil.copy(temp_output, output_path)

    # Cleanup temp file
    if temp_output.exists():
        temp_output.unlink()

    # print("Video processing finished!")

    return output_path