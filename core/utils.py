import uuid
from datetime import datetime
import re
from pathlib import Path


# Generate a file name unique and safe hiding uuid
def generate_safe_filename(original_name: str) -> str:
    ext = original_name.split(".")[-1]
    name = ".".join(original_name.split(".")[:-1])

    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)

    short_id = uuid.uuid4().hex[:6]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"{name}_{timestamp}_{short_id}.{ext}"

# Delete all the files inside the temporary directory

# def clear_temp_directory(temp_dir: Path):
#     for file in temp_dir.iterdir():
#         try:
#             if file.is_file():
#                 file.unlink()
#         except Exception as e:
#             print(f"Could not delete {file}: {e}")
            

# Clear the specified files
def clear_specific_files(file_paths):
    for file in file_paths:
        try:
            if file.exists():
                file.unlink()
        except Exception as e:
            print(f"Could not delete {file}: {e}")