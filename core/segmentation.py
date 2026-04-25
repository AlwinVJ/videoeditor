import cv2
import numpy as np
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# Load model

MODEL_PATH = str(Path(__file__).parent / "models" / "selfie_segmenter.tflite")

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)

options = vision.ImageSegmenterOptions(
    base_options=base_options,
    output_category_mask=True
)

# Create segmenter once (IMPORTANT)
segmenter = vision.ImageSegmenter.create_from_options(options)

def apply_background_effect(frame, effect="blur", bg_image=None):
    # Convert BGR → RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    result = segmenter.segment(mp_image)

    # Get mask
    mask = result.category_mask.numpy_view()

    # Mask handling

    # Normalize (NO inversion)
    mask = mask / 255.0

    # Smooth edges
    mask = cv2.GaussianBlur(mask, (15, 15), 0)

    # Person = lower values → select using <
    condition = mask < 0.5

    # Effects

    if effect == "blur":
        blurred = cv2.GaussianBlur(frame, (55, 55), 0)
        output = np.where(condition[..., None], frame, blurred)

    elif effect == "replace" and bg_image is not None:
        bg_image = cv2.resize(bg_image, (frame.shape[1], frame.shape[0]))
        output = np.where(condition[..., None], frame, bg_image)

    elif effect == "white":
        white_bg = np.ones_like(frame) * 255
        output = np.where(condition[..., None], frame, white_bg)

    else:
        output = frame

    return output