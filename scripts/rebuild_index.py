"""Run with the backend STOPPED: .venv/Scripts/python scripts/rebuild_index.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from src.application import Application
from src.settings import Settings, load_config
from src.utils.logger import configure_logging

if __name__ == '__main__':
    configure_logging()
    app = Application(Settings(), load_config())
    try:
        app.initialize()
        with app.lock:
            chunks = app.repo.searchable_chunks()
            app.vectors.ensure(chunks, force=True)
        print(f'Rebuilt {len(chunks)} vectors. Restart the backend.')
    finally:
        app.close()
