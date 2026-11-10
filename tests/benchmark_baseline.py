import sys
import time
import tracemalloc
from pathlib import Path
import io

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from core.utils import generate_safe_filename, get_file_fingerprint, safe_unlink
from core.video_io import get_video_metadata, process_video


class MockUploadedFile:
    def __init__(self, file_path: Path):
        self.name = file_path.name
        self.data = file_path.read_bytes()
        self.size = len(self.data)

    def getbuffer(self):
        return memoryview(self.data)

    def read(self):
        return self.data


def run_benchmark():
    test_video = ROOT_DIR / "benchmark_sample_1080p.mp4"
    if not test_video.exists():
        print("Test video not found, generating fallback...")
        test_video = ROOT_DIR / "sample.mp4"

    print("==================================================")
    print("BASELINE PERFORMANCE BENCHMARK")
    print(f"Target Video: {test_video.name}")
    print("==================================================")

    # 1. Video Specifications
    metadata = get_video_metadata(test_video)
    file_size_kb = test_video.stat().st_size / 1024.0
    print(f"Duration: {metadata.get('duration')}s")
    print(f"Resolution: {metadata.get('width')}x{metadata.get('height')}")
    print(f"FPS: {metadata.get('fps')}")
    print(f"Total Frames: {metadata.get('total_frames')}")
    print(f"Input File Size: {file_size_kb:.2f} KB ({file_size_kb / 1024:.2f} MB)")

    # 2. Upload & Server-side file-saving benchmark
    print("\n--- 1. UPLOAD & SERVER-SIDE HANDLING ---")
    mock_upload = MockUploadedFile(test_video)

    t0_wall = time.perf_counter()
    # Simulate current uploader logic: fingerprint + disk write + metadata extraction
    fp = get_file_fingerprint(mock_upload.name, mock_upload.size)
    temp_target = ROOT_DIR / "temp" / f"bench_{mock_upload.name}"
    temp_target.parent.mkdir(parents=True, exist_ok=True)
    with open(temp_target, "wb") as f:
        f.write(mock_upload.getbuffer())
    meta = get_video_metadata(temp_target)
    save_duration = time.perf_counter() - t0_wall
    print(f"Server-Side File-Saving & Validation Duration: {save_duration * 1000:.2f} ms")

    # 3. Processing Benchmark (Memory & CPU Tracking)
    print("\n--- 2. VIDEO PROCESSING EXECUTION ---")
    output_video = ROOT_DIR / "temp" / "bench_output.mp4"
    safe_unlink(output_video)

    tracemalloc.start()
    t0_wall = time.perf_counter()
    t0_cpu = time.process_time()

    process_video(
        input_path=temp_target,
        output_path=output_video,
        effect="blur",
        blur_strength=51,
    )

    t_wall = time.perf_counter() - t0_wall
    t_cpu = time.process_time() - t0_cpu
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    out_size_kb = output_video.stat().st_size / 1024.0 if output_video.exists() else 0.0

    print(f"Processing Wall-Clock Duration: {t_wall:.2f} s")
    print(f"Process CPU Time (user + sys): {t_cpu:.2f} s")
    print(f"Effective CPU Utilization: {(t_cpu / t_wall) * 100:.1f}%")
    print(f"Peak Memory Allocated (Python Traced): {peak_mem / (1024 * 1024):.2f} MB")
    print(f"Processed Video Output Size: {out_size_kb:.2f} KB ({out_size_kb / 1024:.2f} MB)")

    # 4. Preview & Download Loading Benchmark
    print("\n--- 3. PREVIEW & DOWNLOAD LOADING ---")
    t0_prev = time.perf_counter()
    with open(output_video, "rb") as f:
        data = f.read()
    preview_latency = time.perf_counter() - t0_prev
    print(f"Preview / Download Buffer Read Time: {preview_latency * 1000:.2f} ms")
    print(f"Preview Bytes Serialized: {len(data) / 1024:.2f} KB")

    # Cleanup
    safe_unlink(temp_target)
    safe_unlink(output_video)
    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    run_benchmark()
