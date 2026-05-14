import cv2
import shutil
from pathlib import Path
from core.audio import merge_audio
from concurrent.futures import ProcessPoolExecutor
from core.worker import process_single_frame, initialize_worker
import time, os, multiprocessing

multiprocessing.set_start_method(
    "spawn",
    force=True
)


def process_video(
    input_path: Path,
    output_path: Path,
    effect="blur",
    bg_image=None,
    blur_strength=51,
    progress_callback=None,
):
    start_time = time.time()
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

    # Conservative worker count
    cpu_count = os.cpu_count() or 4
    max_workers = max(1, min(cpu_count - 1, 4))

    print(f"Using {max_workers} workers")

    batch_size = 12

    temp_output = output_path.parent / f"temp_{output_path.name}"

    # Define codec and output
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(temp_output), fourcc, fps, (width, height))

    frame_count = 0

    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=initialize_worker,
        initargs=(effect, bg_image, blur_strength),
    ) as executor:

        while True:
            batch_frames = []
    
            # Read Batch
            for _ in range(batch_size):
        
                ret, frame = cap.read()
        
                if not ret:
                    break
        
                batch_frames.append(frame)
        
            if len(batch_frames)==0:
                break
        
            frame_start = time.time()
        
            # Parallel processing
            futures = executor.map(
            process_single_frame,
            batch_frames,
            chunksize=4
            )
            
            processed_batch = []
            
            for frame in futures:
                processed_batch.append(frame)
                
            if len(processed_batch) != len(batch_frames):
                print(
                    f"WARNING: Lost frames "
                    f"{len(processed_batch)}/"
                    f"{len(batch_frames)}"
                )
                    
            # Write processed frames
            for processed_frame in processed_batch:
        
                write_start = time.time()
        
                out.write(processed_frame)
        
                frame_count += 1
        
                write_time = time.time() - write_start
        
                # Streamlit progress
                if progress_callback and total_frames > 0:
                    if frame_count % 5 == 0 or frame_count == total_frames:
                        progress_callback(
                            min(frame_count / total_frames, 1.0)
                        )
        
    frame_time = time.time() - frame_start

    # Debug logs
    if frame_count % 30 == 0:
        elapsed = time.time() - start_time
        fps_processing = frame_count / elapsed

        print(
            f"Processed {frame_count} frames | "
            f"Avg Speed: {fps_processing:.2f} FPS | "
            f"Batch: {frame_time:.3f}s | "
            f"Write: {write_time:.3f}s"
        )

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

    total_time = time.time() - start_time

    print("\n===== PERFORMANCE REPORT =====")
    print(f"Total Frames: {frame_count}")
    print(f"Total Time: {total_time:.2f} sec")
    print(f"Average FPS: {frame_count / total_time:.2f}")
    print("==============================")

    return output_path
