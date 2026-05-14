import asyncio
from multiprocessing import freeze_support

from app.main import run_app

if __name__ == "__main__":
    freeze_support()
    
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )
    
    run_app()