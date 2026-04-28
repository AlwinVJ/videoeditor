import sys
from pathlib import Path

# Add root directory to python path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

# Execute the actual app module
app_path = ROOT_DIR / "app" / "main.py"
with open(app_path, "r", encoding="utf-8") as f:
    exec(f.read())
