from multiprocessing import freeze_support

from app.main import run_app

if __name__ == "__main__":
    freeze_support()
    run_app()