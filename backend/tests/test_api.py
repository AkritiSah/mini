import pymupdf
from src.vectordb.vector_store import VectorStore


def upload(client, filename='guide.txt', content=b'Organic ginger cultivation. Use compost for ginger farming.', **metadata):
    return client.post('/api/documents/upload', files={'file': (filename, content)}, data=metadata)


def test_complete_lifecycle_and_restart(client, application):
    response = upload(client, title='Test ginger guide', source_organization='Test fixture, not official')
    assert response.status_code == 202
    ids = response.json()
    assert client.get('/api/jobs/' + ids['job_id']).json()['status'] == 'completed'
    records = client.get('/api/documents').json()
    assert records['document_count'] == records['chunk_count'] == 1
    assert records['documents'][0]['status'] == 'indexed'
    assert 'local_path' not in records['documents'][0]
    assert application.vectors.index.ntotal == 1
    before = application.embedder.calls
    restored = VectorStore(application.settings.index_path, application.embedder)
    restored.ensure(application.repo.searchable_chunks())
    assert application.embedder.calls == before
    result = client.post('/api/chat', json={'question': 'How do I grow organic ginger?'}).json()
    assert result['evidence_status'] == 'supported'
    citation = result['citations'][0]
    assert client.get('/api/sources/' + citation['chunk_id']).json()['source_organization'] == 'Test fixture, not official'
    assert client.get('/api/documents/' + ids['document_id'] + '/file').status_code == 200
    assert client.post('/api/documents/' + ids['document_id'] + '/reindex').status_code == 202
    assert application.vectors.index.ntotal == 1
    assert client.delete('/api/documents/' + ids['document_id']).json()['deleted'] is True
    assert application.vectors.index.ntotal == 0
    assert application.repo.db.chunks.count_documents({}) == 0
    assert client.post('/api/chat', json={'question': 'How do I grow organic ginger?'}).json()['evidence_status'] == 'insufficient'


def test_duplicate_malformed_and_unsafe_upload(client):
    assert upload(client).status_code == 202
    assert upload(client).status_code == 409
    assert upload(client, '../guide.txt').status_code == 400
    assert upload(client, 'fake.pdf', b'not a PDF').status_code == 400
    assert upload(client, 'guide.exe').status_code == 400
    assert upload(client, 'empty.txt', b'').status_code == 400
    assert upload(client, source_url='javascript:alert(1)').status_code == 400


def test_english_document_with_bilingual_header_is_indexed_and_cited(client):
    content = ('(मध्य भारती) English farming research. Organic ginger cultivation uses compost '
               'for soil health. Rishi kheti is a traditional farming method.').encode('utf-8')
    uploaded = upload(client, 'research.txt', content, title='Organic ginger research').json()
    job = client.get('/api/jobs/' + uploaded['job_id']).json()
    assert job['status'] == 'completed'
    result = client.post('/api/chat', json={'question': 'How do I grow organic ginger?'}).json()
    assert result['evidence_status'] == 'supported'
    citation = result['citations'][0]
    assert citation['document_id'] == uploaded['document_id']
    source = client.get('/api/sources/' + citation['chunk_id']).json()
    assert source['original_text'].split() == content.decode('utf-8').split()


def test_pdf_ingestion_and_scan_error(client):
    with pymupdf.open() as document:
        document.new_page().insert_text((50, 50), 'Organic ginger farming uses compost for soil health.')
        content = document.tobytes()
    assert upload(client, 'GUIDE.PDF', content).status_code == 202
    assert client.get('/api/documents').json()['chunk_count'] == 1
    with pymupdf.open() as document:
        document.new_page()
        content = document.tobytes()
    result = upload(client, 'scan.pdf', content).json()
    job = client.get('/api/jobs/' + result['job_id']).json()
    assert job['status'] == 'failed' and 'OCR' in job['error']


def test_languages_filters_and_request_validation(client):
    upload(client, crop='ginger')
    assert client.post('/api/chat', json={'question': 'Write Python code'}).json()['evidence_status'] == 'out_of_scope'
    for question, language in [('सिक्किममा अदुवा खेती कसरी गर्ने?', 'ne'), ('Sikkim ma organic aduwa kheti kasari garne?', 'ne-Latn')]:
        result = client.post('/api/chat', json={'question': question}).json()
        assert result['detected_language'] == language and result['evidence_status'] == 'supported'
    assert client.post('/api/chat', json={'question': 'How do I grow ginger?', 'filters': {'crop': 'rice'}}).json()['evidence_status'] == 'insufficient'
    assert client.post('/api/chat', json={'question': '   '}).status_code == 422
    assert client.get('/api/documents/missing').status_code == 404
    assert client.get('/api/health').json()['mongodb'] is True


def test_forged_citation_is_not_returned(client, application, monkeypatch):
    upload(client)
    from src.llm.llm_client import Completion
    monkeypatch.setattr(application.llm, 'complete', lambda *a, **kw: Completion('Use synthetic fertilizer. [999]', 'fixture', 'fixture'))
    answer = client.post('/api/chat', json={'question': 'How do I grow organic ginger?'}).json()
    assert answer['evidence_status'] == 'insufficient' and answer['citations'] == []


def test_grouped_citations_include_all_referenced_documents(client, application, monkeypatch):
    upload(client, 'guide.txt', b'Organic ginger cultivation. Use compost before planting.')
    upload(client, 'mulch.txt', b'Organic ginger cultivation. Use organic mulch after planting.')
    from src.llm.llm_client import Completion
    def complete(prompt, system, **kwargs):
        answer = '{"supported": true}' if system.startswith('Audit') else 'Use compost and organic mulch [1, 2].'
        return Completion(answer, 'fixture', 'fixture')
    monkeypatch.setattr(application.llm, 'complete', complete)
    result = client.post('/api/chat', json={'question': 'How do I grow organic ginger?'}).json()
    assert result['evidence_status'] == 'supported'
    assert {c['id'] for c in result['citations']} == {1, 2}
    assert len({c['document_id'] for c in result['citations']}) == 2
    for citation in result['citations']:
        assert client.get('/api/sources/' + citation['chunk_id']).status_code == 200
        assert client.get('/api/documents/' + citation['document_id'] + '/file').status_code == 200


def test_existing_sources_remain_available_during_embedding(client, application, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    assert upload(client).status_code == 202
    started, release = Event(), Event()
    encode = application.embedder.encode
    def paused_encode(texts):
        started.set()
        if not release.wait(10):
            raise RuntimeError('Test did not release embedding')
        return encode(texts)
    monkeypatch.setattr(application.embedder, 'encode', paused_encode)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(upload, client, 'next.txt', b'Organic rice cultivation requires irrigation.')
        try:
            assert started.wait(5)
            library = pool.submit(client.get, '/api/documents').result(timeout=3)
            assert library.status_code == 200
            assert any(doc['status'] == 'processing' for doc in library.json()['documents'])
            answer = pool.submit(client.post, '/api/chat', json={'question': 'How do I grow organic ginger?'}).result(timeout=3)
            assert answer.json()['evidence_status'] == 'supported'
            assert len(answer.json()['citations']) == 1
        finally:
            release.set()
        assert pending.result(timeout=5).status_code == 202
    assert application.repo.db.documents.count_documents({'status': 'indexed'}) == 2
    assert application.vectors.index.ntotal == 2


def test_deleting_during_embedding_does_not_restore_document(client, application, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from pathlib import Path
    started, release = Event(), Event()
    encode = application.embedder.encode
    def paused_encode(texts):
        started.set()
        if not release.wait(10):
            raise RuntimeError('Test did not release embedding')
        return encode(texts)
    monkeypatch.setattr(application.embedder, 'encode', paused_encode)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(upload, client)
        try:
            assert started.wait(5)
            doc = application.repo.db.documents.find_one({'filename': 'guide.txt'})
            deleted = pool.submit(client.delete, '/api/documents/' + doc['_id']).result(timeout=3)
            assert deleted.status_code == 200
        finally:
            release.set()
        assert pending.result(timeout=5).status_code == 202
    assert application.repo.db.documents.count_documents({}) == 0
    assert application.repo.db.chunks.count_documents({}) == 0
    assert application.repo.db.ingestion_jobs.count_documents({}) == 0
    assert not Path(doc['local_path']).exists()


def test_health_reads_cached_gemini_connection_without_rechecking(client, application, monkeypatch):
    from unittest.mock import MagicMock
    from google import genai
    from src.llm.llm_client import LLMClient
    from src.settings import Settings
    constructor = MagicMock()
    monkeypatch.setattr(genai, 'Client', constructor)
    llm = LLMClient(Settings(_env_file=None, gemini_api_key='test'), {})
    application.llm = llm
    llm.initialize()
    for _ in range(3):
        response = client.get('/api/health')
        assert response.json()['llm_connection'] == 'ready'
        assert set(response.json()['providers']) == {'gemini'}
    constructor.return_value.models.get.assert_called_once()
    constructor.return_value.models.generate_content.assert_not_called()


def test_interrupted_ingestion_recovers_as_failed(application):
    application.repo.db.documents.insert_one({'_id': 'interrupted', 'status': 'processing', 'file_hash': 'abc'})
    application.repo.db.chunks.insert_one({'_id': 'orphan', 'document_id': 'interrupted'})
    application.initialize()
    assert application.repo.document('interrupted')['status'] == 'failed'
    assert application.repo.db.chunks.count_documents({}) == 0
