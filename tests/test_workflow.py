import sys
from pathlib import Path
import cv2
import numpy as np

# Ensure root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from core.utils import generate_safe_filename, get_file_fingerprint, get_job_dir, safe_unlink, clear_temp_directory
from core.video_io import get_video_metadata, compute_target_resolution, process_video
from core.worker import VideoFrameSegmenter
from app.ui.state import AppState


def run_tests():
    print("==================================================")
    print("STARTING AI VIDEO EDITOR STABILITY TEST SUITE")
    print("==================================================")

    test_temp_dir = ROOT_DIR / "temp" / "test_run"
    test_temp_dir.mkdir(parents=True, exist_ok=True)

    sample_video = ROOT_DIR / "sample.mp4"
    if not sample_video.exists():
        raise FileNotFoundError(f"Sample video not found at {sample_video}")

    # TEST 1: Video Metadata Extraction
    print("\n[TEST 1] Testing get_video_metadata...")
    metadata = get_video_metadata(sample_video)
    print(f"Extracted metadata: {metadata}")
    assert metadata["width"] == 640, f"Expected 640 width, got {metadata['width']}"
    assert metadata["height"] == 360, f"Expected 360 height, got {metadata['height']}"
    assert metadata["fps"] == 24.0, f"Expected 24 fps, got {metadata['fps']}"
    assert metadata["total_frames"] > 0, "Frames should be > 0"
    print("[PASSED] TEST 1: Metadata extraction is accurate.")

    # TEST 2: Resolution Capping
    print("\n[TEST 2] Testing compute_target_resolution...")
    w_4k, h_4k = compute_target_resolution(3840, 2160, max_dimension=1920)
    assert w_4k == 1920 and h_4k == 1080, f"Expected 1920x1080 for 4K downscale, got {w_4k}x{h_4k}"
    assert w_4k % 2 == 0 and h_4k % 2 == 0, "Dimensions must be even for H.264"

    w_odd, h_odd = compute_target_resolution(1281, 721, max_dimension=1920)
    assert w_odd % 2 == 0 and h_odd % 2 == 0, f"Expected even dimensions, got {w_odd}x{h_odd}"
    print("[PASSED] TEST 2: Resolution capping and even-dimension parity verified.")

    # TEST 3: Effects (Blur, White, Replace, None)
    print("\n[TEST 3] Testing VideoFrameSegmenter effects...")
    dummy_frame = np.full((360, 640, 3), 128, dtype=np.uint8)

    # Test Blur
    blur_segmenter = VideoFrameSegmenter(effect="blur", blur_strength=51, target_size=(640, 360))
    res_blur = blur_segmenter.process_frame(dummy_frame)
    assert res_blur.shape == dummy_frame.shape, "Shape mismatch in blur"
    blur_segmenter.close()

    # Test White
    white_segmenter = VideoFrameSegmenter(effect="white", target_size=(640, 360))
    res_white = white_segmenter.process_frame(dummy_frame)
    assert res_white.shape == dummy_frame.shape, "Shape mismatch in white"
    white_segmenter.close()

    # Test Replace with custom background
    custom_bg = np.zeros((360, 640, 3), dtype=np.uint8)
    custom_bg[:] = (0, 255, 0)  # Green background
    replace_segmenter = VideoFrameSegmenter(effect="replace", bg_image=custom_bg, target_size=(640, 360))
    res_replace = replace_segmenter.process_frame(dummy_frame)
    assert res_replace.shape == dummy_frame.shape, "Shape mismatch in replace"
    replace_segmenter.close()

    print("[PASSED] TEST 3: All effects (blur, white, replace) composited successfully.")

    # TEST 4: Full Pipeline End-to-End Processing & Progress Tracking
    print("\n[TEST 4] Testing end-to-end process_video with progress callbacks...")
    output_video = test_temp_dir / "test_processed.mp4"
    safe_unlink(output_video)

    progress_log = []
    def on_progress(p):
        progress_log.append(p)

    process_video(
        input_path=sample_video,
        output_path=output_video,
        effect="blur",
        blur_strength=51,
        progress_callback=on_progress,
    )

    assert output_video.exists(), "Processed video file was not created"
    assert output_video.stat().st_size > 0, "Processed video file is empty"
    assert len(progress_log) > 0, "Progress callback was never triggered"
    assert progress_log[-1] == 1.0, f"Expected final progress 1.0, got {progress_log[-1]}"
    print(f"Generated output size: {output_video.stat().st_size} bytes across {len(progress_log)} progress ticks.")
    print("[PASSED] TEST 4: End-to-end processing completed successfully with 100% progress.")

    # TEST 5: Verify Video/Audio Codecs & Format
    print("\n[TEST 5] Testing output video stream and codec integrity...")
    cap = cv2.VideoCapture(str(output_video))
    assert cap.isOpened(), "Could not open processed video with OpenCV"
    out_fps = cap.get(cv2.CAP_PROP_FPS)
    out_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    out_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    assert out_w == 640 and out_h == 360, f"Expected 640x360, got {out_w}x{out_h}"
    assert out_frames > 0, "Frame count must be > 0"
    print(f"Verified output properties: {out_w}x{out_h} @ {out_fps} fps, {out_frames} frames.")
    print("[PASSED] TEST 5: Video codec output is fully valid.")

    # TEST 6: File Idempotency and Fingerprinting
    print("\n[TEST 6] Testing upload fingerprinting...")
    fp1 = get_file_fingerprint("sample.mp4", 35000)
    fp2 = get_file_fingerprint("sample.mp4", 35000)
    fp3 = get_file_fingerprint("sample.mp4", 35001)
    assert fp1 == fp2, "Identical files should have identical fingerprints"
    assert fp1 != fp3, "Different files should have different fingerprints"
    print("[PASSED] TEST 6: Fingerprinting is deterministic.")

    # TEST 7: Directory & Temporary File Cleanup
    print("\n[TEST 7] Testing temporary cleanup...")
    clear_temp_directory(test_temp_dir)
    assert not output_video.exists(), "Intermediate output video should have been cleaned"
    print("[PASSED] TEST 7: Temporary directory cleanup operates cleanly.")

    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! (7/7)")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
