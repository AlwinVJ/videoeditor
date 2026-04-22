import uuid
from datetime import datetime
import re


def generate_safe_filename(original_name: str) -> str:
    ext = original_name.split(".")[-1]
    name = ".".join(original_name.split(".")[:-1])

    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)

    short_id = uuid.uuid4().hex[:6]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"{name}_{timestamp}_{short_id}.{ext}"