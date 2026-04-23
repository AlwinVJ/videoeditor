from pathlib import Path
from core.video_io import process_video

input_path = Path("sample.mp4")
output_path = Path("output.mp4")

process_video(input_path, output_path)

print("Done!")