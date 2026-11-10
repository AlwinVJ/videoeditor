import os

# Limit CPU thread contention for cgroups container environments
os.environ["GLOG_minloglevel"] = "2"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

from pathlib import Path
import cv2
import numpy as np

# Clamp OpenCV internal thread pool to 1 thread to avoid host oversubscription
cv2.setNumThreads(1)

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_PATH = str(Path(__file__).parent / "models" / "selfie_segmenter.tflite")

# Cached singleton segmenter to avoid re-parsing TFLite weights on every run
_SHARED_IMAGE_SEGMENTER = None

worker_effect = "none"
worker_bg_image = None
worker_blur_strength = 51


def get_shared_segmenter():
    """Retrieve or lazily create the shared MediaPipe ImageSegmenter instance."""
    global _SHARED_IMAGE_SEGMENTER
    if _SHARED_IMAGE_SEGMENTER is None:
        base_options = python.BaseOptions(
            model_asset_path=MODEL_PATH,
            delegate=python.BaseOptions.Delegate.CPU,
        )
        options = vision.ImageSegmenterOptions(
            base_options=base_options,
            output_category_mask=True,
        )
        _SHARED_IMAGE_SEGMENTER = vision.ImageSegmenter.create_from_options(options)
    return _SHARED_IMAGE_SEGMENTER


class VideoFrameSegmenter:
    """High-performance in-process frame segmenter and compositor with temporal mask reuse."""

    def __init__(
        self,
        effect="none",
        bg_image=None,
        blur_strength=51,
        target_size=None,
        frame_stride: int = 2,
    ):
        self.effect = effect
        self.blur_strength = blur_strength if blur_strength % 2 == 1 else blur_strength + 1
        self.target_size = target_size  # (width, height)
        self.frame_stride = max(1, frame_stride)
        self.frame_idx = 0
        self.cached_mask = None

        # Pre-scale background image once if target size is known
        self.bg_image = None
        if bg_image is not None:
            if target_size is not None and bg_image.shape[:2] != (target_size[1], target_size[0]):
                self.bg_image = cv2.resize(bg_image, target_size, interpolation=cv2.INTER_LINEAR)
            else:
                self.bg_image = bg_image

        # Use shared cached segmenter
        self.segmenter = get_shared_segmenter()

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        if self.effect == "none":
            return frame

        h, w = frame.shape[:2]

        # Ensure background image matches frame resolution
        if self.effect == "replace" and self.bg_image is not None:
            if self.bg_image.shape[:2] != (h, w):
                self.bg_image = cv2.resize(self.bg_image, (w, h), interpolation=cv2.INTER_LINEAR)

        # Run AI inference on stride frames, reuse cached mask on intervening frames
        needs_inference = (
            self.cached_mask is None
            or (self.frame_idx % self.frame_stride == 0)
        )

        if needs_inference:
            # Downsample to 256x256 for optimal MediaPipe inference speed (>150 FPS)
            small_frame = cv2.resize(frame, (256, 256), interpolation=cv2.INTER_LINEAR)
            rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            result = self.segmenter.segment(mp_image)
            raw_mask = result.category_mask.numpy_view()

            # Upscale mask back to original resolution with nearest neighbor
            self.cached_mask = cv2.resize(raw_mask, (w, h), interpolation=cv2.INTER_NEAREST)

        self.frame_idx += 1
        condition = (self.cached_mask < 0.5)[..., None]

        if self.effect == "blur":
            blur_w = max(16, w // 4)
            blur_h = max(16, h // 4)
            small_blur = cv2.resize(frame, (blur_w, blur_h), interpolation=cv2.INTER_LINEAR)
            blurred_small = cv2.GaussianBlur(
                small_blur, (self.blur_strength, self.blur_strength), 0
            )
            blurred = cv2.resize(blurred_small, (w, h), interpolation=cv2.INTER_LINEAR)
            output = np.where(condition, frame, blurred)

        elif self.effect == "replace" and self.bg_image is not None:
            output = np.where(condition, frame, self.bg_image)

        elif self.effect == "white":
            output = np.where(condition, frame, 255)

        else:
            output = frame

        return output

    def close(self):
        # Retain shared segmenter in memory for instant reuse
        pass


def initialize_worker(effect, bg_image, blur_strength):
    """Backward-compatible initialization for multiprocessing if invoked."""
    global worker_effect, worker_bg_image, worker_blur_strength
    worker_effect = effect
    worker_blur_strength = blur_strength if blur_strength % 2 == 1 else blur_strength + 1
    worker_bg_image = bg_image
    get_shared_segmenter()


def process_single_frame(frame):
    """Backward-compatible single-frame processor."""
    global worker_bg_image
    segmenter_inst = get_shared_segmenter()

    h, w = frame.shape[:2]
    small_frame = cv2.resize(frame, (256, 256), interpolation=cv2.INTER_LINEAR)
    rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    result = segmenter_inst.segment(mp_image)
    mask = result.category_mask.numpy_view()
    mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    condition = (mask < 0.5)[..., None]

    if worker_effect == "blur":
        blur_w = max(16, w // 4)
        blur_h = max(16, h // 4)
        small_blur = cv2.resize(frame, (blur_w, blur_h))
        k = worker_blur_strength if worker_blur_strength % 2 == 1 else worker_blur_strength + 1
        blurred_small = cv2.GaussianBlur(small_blur, (k, k), 0)
        blurred = cv2.resize(blurred_small, (w, h))
        return np.where(condition, frame, blurred)

    elif worker_effect == "replace" and worker_bg_image is not None:
        if worker_bg_image.shape[:2] != (h, w):
            worker_bg_image = cv2.resize(worker_bg_image, (w, h))
        return np.where(condition, frame, worker_bg_image)

    elif worker_effect == "white":
        return np.where(condition, frame, 255)

    return frame
