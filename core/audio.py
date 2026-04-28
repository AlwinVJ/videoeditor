import subprocess
import imageio_ffmpeg as ffmpeg


def merge_audio(original_video, processed_video, final_output):
    ffmpeg_path = ffmpeg.get_ffmpeg_exe()

    command = [
        ffmpeg_path,
        "-y",
        "-i", str(processed_video),
        "-i", str(original_video),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-pix_fmt", "yuv420p",
        str(final_output)
    ]

    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)