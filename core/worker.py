import cv2
import numpy as np
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


MODEL_PATH = str(
    Path(__file__).parent / "models" / "selfie_segmenter.tflite"
)

base_options = python.BaseOptions(
    model_asset_path=MODEL_PATH
)

options = vision.ImageSegmenterOptions(
    base_options=base_options,
    output_category_mask=True
)

segmenter = vision.ImageSegmenter.create_from_options(
    options
)


def process_single_frame(args):

    (
        frame,
        effect,
        bg_image,
        blur_strength
    ) = args

    # Resize for segmentation
    scale = 0.5

    small_frame = cv2.resize(
        frame,
        None,
        fx=scale,
        fy=scale
    )

    rgb_frame = cv2.cvtColor(
        small_frame,
        cv2.COLOR_BGR2RGB
    )

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    result = segmenter.segment(mp_image)

    mask = result.category_mask.numpy_view()

    mask = cv2.resize(
        mask,
        (frame.shape[1], frame.shape[0])
    )

    mask = cv2.GaussianBlur(
        mask,
        (15, 15),
        0
    )

    condition = mask < 0.5

    if effect == "blur":

        blur_scale = 0.25

        small_blur_frame = cv2.resize(
            frame,
            None,
            fx=blur_scale,
            fy=blur_scale
        )

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

        bg_image = cv2.resize(
            bg_image,
            (frame.shape[1], frame.shape[0])
        )

        output = np.where(
            condition[..., None],
            frame,
            bg_image
        )

    elif effect == "white":

        white_bg = np.ones_like(frame) * 255

        output = np.where(
            condition[..., None],
            frame,
            white_bg
        )

    else:
        output = frame

    return output