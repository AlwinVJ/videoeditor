import asyncio
import platform
from multiprocessing import freeze_support

from app.main import run_app


if __name__ == "__main__":
    freeze_support()

    # Windows-only event loop fix
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()
        )

    run_app()