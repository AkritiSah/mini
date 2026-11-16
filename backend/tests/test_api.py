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


def test_interrupted_ingestion_recovers_as_failed(application):
    application.repo.db.documents.insert_one({'_id': 'interrupted', 'status': 'processing', 'file_hash': 'abc'})
    application.repo.db.chunks.insert_one({'_id': 'orphan', 'document_id': 'interrupted'})
    application.initialize()
    assert application.repo.document('interrupted')['status'] == 'failed'
    assert application.repo.db.chunks.count_documents({}) == 0
