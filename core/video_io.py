import cv2
from pathlib import Path
from core.segmentation import apply_background_effect


def process_video(input_path: Path, output_path: Path, effect = "blur"):
    cap = cv2.VideoCapture(str(input_path))

    if not cap.isOpened():
        raise ValueError("Error opening video file")

    # Video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps > 0 else 24  # fallback

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Codec
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        processed = apply_background_effect(frame, effect= effect)

        out.write(processed)

    cap.release()
    out.release()

    return output_path