"""Download and verify project-local OCR models; no system install is required."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from src.ingestion.ocr import ensure_models
from src.settings import load_config


if __name__ == '__main__':
    config = load_config().get('ocr', {})
    folder = ensure_models(config.get('languages', 'eng+nep'))
    print(f'English/Nepali OCR models ready: {folder}')
