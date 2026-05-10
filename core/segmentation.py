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

# Create segmenter once
segmenter = vision.ImageSegmenter.create_from_options(options)
last_mask = None

def apply_background_effect(frame, effect="blur", bg_image=None, blur_strength = 51, frame_count=0,segment_every=2):
    
    scale = 0.5

    small_frame = cv2.resize(
        frame,
        None,
        fx=scale,
        fy=scale
    )
    
    # Convert BGR → RGB
    rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    global last_mask

    # Segment only every N frames
    if frame_count % segment_every == 0 or last_mask is None:
    
        result = segmenter.segment(mp_image)
    
        mask = result.category_mask.numpy_view()
    
        mask = cv2.resize(
            mask,
            (frame.shape[1], frame.shape[0])
        )
    
        last_mask = mask
    
    else:
        mask = last_mask

    # Mask handling

    # Normalize (NO inversion)
    mask = mask / 255.0

    # Smooth edges
    mask = cv2.GaussianBlur(mask, (15, 15), 0)

    # Person = lower values → select using <
    condition = mask < 0.5

    # Effects

    if effect == "blur":

        blur_scale = 0.25
    
        small_blur_frame = cv2.resize(
            frame,
            None,
            fx=blur_scale,
            fy=blur_scale
        )
    
        # Make kernel odd
        if blur_strength % 2 == 0:
            blur_strength += 1
    
        blurred_small = cv2.GaussianBlur(
            small_blur_frame,
            (blur_strength, blur_strength),
            0
        )
    
        blurred = cv2.resize(
            blurred_small,
            (frame.shape[1], frame.shape[0])
        )
    
        output = np.where(
            condition[..., None],
            frame,
            blurred
        )

    elif effect == "replace" and bg_image is not None:
        bg_image = cv2.resize(bg_image, (frame.shape[1], frame.shape[0]))
        output = np.where(condition[..., None], frame, bg_image)

    elif effect == "white":
        white_bg = np.ones_like(frame) * 255
        output = np.where(condition[..., None], frame, white_bg)

    else:
        output = frame

    return output