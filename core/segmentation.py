import cv2
import mediapipe as mp
import numpy as np

mp_selfie_segmentation = mp.solutions.selfie_segmentation


def apply_background_effect(frame, effect="blur", bg_image=None):
    with mp_selfie_segmentation.SelfieSegmentation(model_selection=1) as segmenter:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = segmenter.process(rgb_frame)

        mask = results.segmentation_mask

        # Create binary mask
        condition = mask > 0.5

        if effect == "blur":
            blurred = cv2.GaussianBlur(frame, (55, 55), 0)
            output = np.where(condition[..., None], frame, blurred)

        elif effect == "replace" and bg_image is not None:
            bg_image = cv2.resize(bg_image, (frame.shape[1], frame.shape[0]))
            output = np.where(condition[..., None], frame, bg_image)

        else:
            output = frame

        return output