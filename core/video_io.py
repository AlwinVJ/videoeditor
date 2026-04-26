import cv2
from pathlib import Path
from core.segmentation import apply_background_effect


def process_video(input_path: Path, output_path: Path, effect="blur", bg_image=None):
    # Open video
    cap = cv2.VideoCapture(str(input_path))

    if not cap.isOpened():
        raise ValueError("Error opening video file")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps > 0 else 24

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Define codec and output
    fourcc = cv2.VideoWriter_fourcc(*"vp80")
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

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

        # Optional debug (remove later)
        if frame_count % 30 == 0:
            print(f"Processed {frame_count} frames")

    # Release resources
    cap.release()
    out.release()

    # print("Video processing finished!")

    return output_path