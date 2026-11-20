import hashlib
import io
from unittest.mock import Mock

import pymupdf
import pytest

from src.ingestion import ocr
from src.ingestion.parsers import parse


def scanned_pdf(path, *, mixed=False, header=False):
    with pymupdf.open() as source:
        source.new_page().insert_text((45, 80), 'Organic potato cultivation uses healthy seed potatoes.', fontsize=15)
        image = source[0].get_pixmap(dpi=120).tobytes('png')
    with pymupdf.open() as document:
        if mixed:
            document.new_page().insert_text((45, 80), 'Original digital text about potato farming.')
        page = document.new_page()
        page.insert_image(page.rect, stream=image)
        if header:
            page.insert_text((45, 40), 'Potato farming handbook and cultivation guidance')
        document.save(path)


@pytest.mark.parametrize('header', [False, True])
def test_mixed_pdf_keeps_digital_text_and_ocrs_scanned_page(tmp_path, monkeypatch, header):
    path = tmp_path / 'mixed.pdf'
    scanned_pdf(path, mixed=True, header=header)
    prepare = Mock(return_value=tmp_path)
    read = Mock(return_value='आलु खेतीका लागि स्वस्थ बीउ र पानीको राम्रो निकास भएको माटो चाहिन्छ।')
    monkeypatch.setattr(ocr, 'ensure_models', prepare)
    monkeypatch.setattr(ocr, 'read_page', read)
    progress = Mock()
    sections = parse(path, on_page=progress)
    assert sections[0].text.strip() == 'Original digital text about potato farming.'
    assert sections[1].text.startswith('आलु खेती')
    assert [section.page for section in sections] == [1, 2]
    prepare.assert_called_once_with('eng+nep')
    read.assert_called_once()
    assert progress.call_args_list[-1].args == (2, 2, True)


def test_ocr_disabled_reports_how_to_recover(tmp_path, monkeypatch):
    path = tmp_path / 'scan.pdf'
    scanned_pdf(path)
    prepare = Mock()
    monkeypatch.setattr(ocr, 'ensure_models', prepare)
    with pytest.raises(ValueError, match='Enable ocr.enabled'):
        parse(path, ocr_config={'enabled': False})
    prepare.assert_not_called()


def test_blank_pdf_does_not_download_models(tmp_path, monkeypatch):
    path = tmp_path / 'blank.pdf'
    with pymupdf.open() as document:
        document.new_page()
        document.save(path)
    prepare = Mock()
    monkeypatch.setattr(ocr, 'ensure_models', prepare)
    with pytest.raises(ValueError, match='no readable text'):
        parse(path)
    prepare.assert_not_called()


def test_ocr_model_download_is_verified_and_reused(tmp_path, monkeypatch):
    payload = b'test-only model fixture'
    monkeypatch.setattr(ocr, 'MODEL_HASHES', {'nep': hashlib.sha256(payload).hexdigest()})
    download = Mock(return_value=io.BytesIO(payload))
    monkeypatch.setattr(ocr, 'urlopen', download)
    assert ocr.ensure_models('nep', tmp_path) == tmp_path
    assert (tmp_path / 'nep.traineddata').read_bytes() == payload
    ocr.ensure_models('nep', tmp_path)
    download.assert_called_once()


def test_corrupt_model_is_not_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, 'urlopen', Mock(return_value=io.BytesIO(b'corrupted')))
    with pytest.raises(ValueError, match='setup_ocr.py'):
        ocr.ensure_models('nep', tmp_path)
    assert not (tmp_path / 'nep.traineddata').exists()
    assert not list(tmp_path.glob('*.tmp'))


def test_scanned_upload_is_indexed_with_page_citations(client, tmp_path, monkeypatch):
    path = tmp_path / 'potato.pdf'
    scanned_pdf(path)
    monkeypatch.setattr(ocr, 'ensure_models', lambda *args: tmp_path)
    monkeypatch.setattr(ocr, 'read_page', lambda *args, **kwargs:
                        'Organic potato cultivation uses healthy seed potatoes and well-drained soil.')
    uploaded = client.post('/api/documents/upload', files={'file': ('potato.pdf', path.read_bytes())}).json()
    job = client.get('/api/jobs/' + uploaded['job_id']).json()
    assert job['status'] == 'completed'
    assert job['processed_pages'] == job['total_pages'] == 1
    documents = client.get('/api/documents').json()['documents']
    assert documents[0]['status'] == 'indexed'
    answer = client.post('/api/chat', json={'question': 'How do I grow organic potatoes?'}).json()
    assert answer['evidence_status'] == 'supported'
    citation = answer['citations'][0]
    assert citation['page'] == 1
    assert citation['document_id'] == uploaded['document_id']
