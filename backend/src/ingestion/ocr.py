"""Local OCR using PyMuPDF's bundled Tesseract and verified language models."""
import hashlib
import logging
from pathlib import Path
from threading import Lock
from urllib.request import urlopen
from uuid import uuid4

from src.settings import ROOT


logger = logging.getLogger('krishi')
_model_lock = Lock()
MODEL_RELEASE = '4.1.0'
MODEL_HASHES = {
    'eng': '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2',
    'nep': '280ba9450b4f21afbf5985e0de87857b75a972577c50ef0603c141ddde4f1cb8',
}


def ensure_models(languages='eng+nep', directory=None):
    folder = Path(directory) if directory else ROOT / '.runtime' / 'tessdata'
    requested = languages.split('+')
    if not requested or any(language not in MODEL_HASHES for language in requested):
        raise ValueError('OCR supports eng and nep languages, combined as eng+nep.')
    with _model_lock:
        folder.mkdir(parents=True, exist_ok=True)
        for language in requested:
            path = folder / (language + '.traineddata')
            digest = MODEL_HASHES[language]
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                continue
            temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
            try:
                url = f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{MODEL_RELEASE}/{language}.traineddata'
                logger.info('ocr_language_download language=%s', language)
                with urlopen(url, timeout=30) as response:
                    data = response.read(8_000_001)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError('OCR language download failed its integrity check.')
                temporary.write_bytes(data)
                temporary.replace(path)
            except Exception as error:
                raise ValueError('OCR language data could not be prepared. Connect to the internet and run '
                                 'python scripts/setup_ocr.py, then reindex this document.') from error
            finally:
                temporary.unlink(missing_ok=True)
    return folder


def read_page(page, *, languages, dpi, tessdata):
    # Limit raster size for unusually large pages while retaining normal-page DPI.
    max_pixels = 20_000_000
    pixels = page.rect.width * page.rect.height * (dpi / 72) ** 2
    effective_dpi = max(1, int(dpi * min(1, (max_pixels / max(pixels, 1)) ** .5)))
    try:
        textpage = page.get_textpage_ocr(language=languages, dpi=effective_dpi,
                                        full=True, tessdata=str(tessdata))
        text = page.get_text(textpage=textpage, sort=True)
    except Exception as error:
        raise ValueError(f'Local OCR failed on PDF page {page.number + 1}. '
                         'Check the scan quality and OCR language data, then reindex.') from error
    logger.info('pdf_page_ocr page=%s characters=%s', page.number + 1, len(text))
    return text
