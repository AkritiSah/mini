import json

import pytest

from src.llm.llm_client import Completion, LLMUnavailable
from src.settings import load_config


ENGLISH = 'Organic potato cultivation requires healthy seed potatoes and well-drained soil.'
NEPALI = 'आलु खेतीका लागि स्वस्थ बीउ आलु र पानीको राम्रो निकास भएको माटो चाहिन्छ।'
ROMANIZED = 'Alu kheti kasari garne? Swastha biu ra pani najamne mato chahinchha.'


@pytest.fixture
def potato_llm(application, monkeypatch):
    def complete(prompt, system, max_tokens=None):
        if system.startswith('Translate'):
            answer = ENGLISH
        elif system.startswith('Audit'):
            answer = '{"supported": true}'
        else:
            language = json.loads(prompt)['response_language']
            answer = {
                'en': 'Use healthy seed potatoes and well-drained soil. [1]',
                'ne': 'स्वस्थ बीउ आलु र पानीको राम्रो निकास भएको माटो प्रयोग गर्नुहोस्। [1]',
                'ne-Latn': 'Swastha biu alu ra pani najamne mato prayog garnuhos. [1]',
            }[language]
        return Completion(answer, 'test-fixture', 'offline')

    monkeypatch.setattr(application.llm, 'complete', complete)


@pytest.mark.parametrize('content, language', [(NEPALI, 'ne'), (ROMANIZED, 'ne-Latn')])
def test_default_upload_translates_and_supports_multilingual_queries(
        client, application, potato_llm, content, language):
    response = client.post('/api/documents/upload',
        files={'file': ('potato.txt', content.encode('utf-8'))}, data={'crop': 'potato'})
    assert response.status_code == 202
    ids = response.json()
    assert client.get('/api/jobs/' + ids['job_id']).json()['status'] == 'completed'
    document = application.repo.document(ids['document_id'])
    assert document['status'] == 'indexed'
    assert document['language'] == language
    chunk = application.repo.db.chunks.find_one({'document_id': ids['document_id']})
    assert chunk['original_text'].split() == content.split()
    assert chunk['retrieval_text_en'] == ENGLISH
    assert chunk['language'] == language
    assert chunk['verification_status'] == 'unverified'

    for question, expected_language in [
        ('How do I grow organic potatoes?', 'en'),
        ('आलु खेती कसरी गर्ने?', 'ne'),
        ('Alu kheti kasari garne?', 'ne-Latn'),
    ]:
        response = client.post('/api/chat', json={'question': question})
        assert response.status_code == 200
        answer = response.json()
        assert answer['detected_language'] == expected_language
        assert answer['evidence_status'] == 'supported'
        citation = answer['citations'][0]
        assert citation['document_id'] == ids['document_id']
        source = client.get('/api/sources/' + citation['chunk_id']).json()
        assert source['original_text'].split() == content.split()


def test_failed_nepali_upload_can_be_reindexed_after_enabling_translation(
        client, application, potato_llm):
    application.config['translation']['translate_documents'] = False
    response = client.post('/api/documents/upload',
        files={'file': ('potato.txt', NEPALI.encode('utf-8'))})
    ids = response.json()
    job = client.get('/api/jobs/' + ids['job_id']).json()
    assert job['status'] == 'failed'
    assert 'Enable translation.translate_documents' in job['error']
    assert not application.repo.searchable_chunks()

    application.config['translation'].update(load_config()['translation'])
    response = client.post('/api/documents/' + ids['document_id'] + '/reindex')
    assert response.status_code == 202
    job = client.get('/api/jobs/' + response.json()['job_id']).json()
    assert job['status'] == 'completed'
    document = application.repo.document(ids['document_id'])
    assert document['status'] == 'indexed'
    assert document['error'] is None
    assert len(application.repo.searchable_chunks()) == 1


def test_reindex_resumes_saved_translations_after_rate_limit(client, application, monkeypatch):
    from unittest.mock import Mock
    from src.ingestion import ingestion_service
    from src.ingestion.parsers import Section
    from src.translation.translator import Translator

    application.config['translation']['document_request_interval_seconds'] = 0
    second = 'आलु खेतीमा पानी जम्न नदिनुहोस्।'
    monkeypatch.setattr(ingestion_service, 'load_sections',
                        lambda *args: [Section(NEPALI, 1), Section(second, 2)])
    generate = Mock(side_effect=[Completion(ENGLISH, 'fixture', 'offline'),
        LLMUnavailable('Gemini HTTP 429: rate limit reached.', category='rate_limit', retry_after=45)])
    monkeypatch.setattr(application.llm, 'complete', generate)
    uploaded = client.post('/api/documents/upload',
        files={'file': ('potato.txt', NEPALI.encode('utf-8'))}).json()
    job = client.get('/api/jobs/' + uploaded['job_id']).json()
    assert job['status'] == 'failed'
    assert job['progress'] == 52
    assert job['normalized_chunks'] == 1
    assert job['total_chunks'] == 2
    assert job['error_category'] == 'rate_limit'
    assert job['retry_after_seconds'] == 45
    assert 'Reindex to resume' in job['error']
    assert not application.repo.searchable_chunks()

    # Recreate the translator to ensure resumption uses the database checkpoint.
    application.translator = Translator(application.llm, application.config['translation'])
    generate.reset_mock()
    generate.side_effect = None
    generate.return_value = Completion('Prevent waterlogging in potato fields.', 'fixture', 'offline')
    retried = client.post('/api/documents/' + uploaded['document_id'] + '/reindex').json()
    assert client.get('/api/jobs/' + retried['job_id']).json()['status'] == 'completed'
    generate.assert_called_once()
    assert generate.call_args.args[0] == second
    assert len(application.repo.searchable_chunks()) == 2

    # A fully translated document can be reindexed without any provider requests.
    generate.reset_mock()
    assert client.post('/api/documents/' + uploaded['document_id'] + '/reindex').status_code == 202
    generate.assert_not_called()
    assert client.delete('/api/documents/' + uploaded['document_id']).status_code == 200
    assert application.repo.db.translation_cache.count_documents({}) == 0


def test_translation_cache_is_invalidated_by_model_change(client, application, potato_llm, monkeypatch):
    from unittest.mock import Mock
    application.config['translation']['document_request_interval_seconds'] = 0
    uploaded = client.post('/api/documents/upload',
        files={'file': ('potato.txt', NEPALI.encode('utf-8'))}).json()
    assert client.get('/api/jobs/' + uploaded['job_id']).json()['status'] == 'completed'
    application.settings.gemini_model = 'different-model'
    translate = Mock(return_value=Completion(ENGLISH, 'fixture', 'offline'))
    monkeypatch.setattr(application.llm, 'complete', translate)
    retried = client.post('/api/documents/' + uploaded['document_id'] + '/reindex').json()
    assert client.get('/api/jobs/' + retried['job_id']).json()['status'] == 'completed'
    translate.assert_called_once()
