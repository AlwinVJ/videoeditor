import uuid
from datetime import datetime
import hashlib
import re
import shutil
from pathlib import Path


def generate_safe_filename(original_name: str) -> str:
    """Generate a sanitized, unique filename."""
    parts = original_name.rsplit(".", 1)
    ext = parts[1] if len(parts) > 1 else "mp4"
    name = parts[0]
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)

    short_id = uuid.uuid4().hex[:6]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"{name}_{timestamp}_{short_id}.{ext}"


def get_file_fingerprint(file_name: str, file_size: int) -> str:
    """Generate a stable fingerprint for an uploaded file to avoid redundant re-saves."""
    raw = f"{file_name}_{file_size}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def get_job_dir(base_temp_dir: Path, job_id: str) -> Path:
    """Return and create a dedicated job directory."""
    job_dir = base_temp_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def safe_unlink(file_path: Path):
    """Safely delete a file if it exists without raising exceptions."""
    try:
        if file_path and file_path.exists() and file_path.is_file():
            file_path.unlink()
    except Exception as e:
        print(f"Could not safely delete {file_path}: {e}")


def clear_temp_directory(temp_dir: Path):
    """Delete all files and job subdirectories inside the temporary directory."""
    if not temp_dir.exists():
        return

    for item in temp_dir.iterdir():
        try:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
        except Exception as e:
            print(f"Could not delete {item}: {e}")


def clear_specific_files(file_paths):
    """Clear a list of specific file paths."""
    for file in file_paths:
        try:
            p = Path(file)
            if p.exists() and p.is_file():
                p.unlink()
        except Exception as e:
            print(f"Could not delete {file}: {e}")
