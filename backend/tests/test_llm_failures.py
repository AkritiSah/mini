import logging
from unittest.mock import Mock

import pytest

from src.llm import llm_client
from src.llm.llm_client import LLMClient, LLMUnavailable, failure_details
from src.settings import Settings


def http_error(status):
    error = RuntimeError('private API key and prompt must never be shown')
    error.status_code = status
    return error


def client(**config):
    settings = Settings(_env_file=None, gemini_api_key='test')
    return LLMClient(settings, {'max_output_tokens': 100, 'max_provider_attempts': 2,
                               'provider_cooldown_seconds': 30, **config})


@pytest.mark.parametrize('status,category,retryable', [
    (401, 'authentication', False), (403, 'authentication', False),
    (404, 'model_not_found', False), (400, 'request', False),
    (429, 'rate_limit', True), (503, 'provider_unavailable', True),
    (504, 'timeout', True),
])
def test_failure_classification(status, category, retryable):
    detail = failure_details(http_error(status))
    assert (detail['status'], detail['category'], detail['retryable']) == (status, category, retryable)


def test_connection_cause_is_reported_without_private_error_text():
    error = RuntimeError('private-key')
    error.__cause__ = ConnectionResetError(10054, 'private endpoint')
    detail = failure_details(error)
    assert detail['category'] == 'connection_reset'
    assert detail['cause_type'] == 'ConnectionResetError'
    assert detail['network_errno'] == 10054
    assert 'private' not in str(detail)


def test_transient_retry_omits_private_details(monkeypatch, caplog):
    llm = client()
    generate = Mock(side_effect=[http_error(504), 'answer', 'next answer'])
    sleep = Mock()
    monkeypatch.setattr(llm, '_gemini', generate)
    monkeypatch.setattr(llm_client.time, 'sleep', sleep)
    with caplog.at_level(logging.WARNING, logger='krishi'):
        assert llm.complete('private prompt', 'system').text == 'answer'
        assert llm.complete('next prompt', 'system').text == 'next answer'
    assert generate.call_count == 3
    sleep.assert_called_once()
    assert 'category=timeout' in caplog.text
    assert 'private' not in caplog.text


def test_permanent_failure_is_not_retried_and_cooldown_expires(monkeypatch):
    llm = client()
    clock = [100.0]
    monkeypatch.setattr(llm_client.time, 'monotonic', lambda: clock[0])
    generate = Mock(side_effect=http_error(401))
    monkeypatch.setattr(llm, '_gemini', generate)
    with pytest.raises(LLMUnavailable, match='credentials rejected') as failure:
        llm.complete('prompt', 'system')
    assert 'private' not in str(failure.value)
    with pytest.raises(LLMUnavailable, match='cooling down'):
        llm.complete('prompt', 'system')
    assert generate.call_count == 1
    clock[0] += 31
    generate.side_effect = None
    generate.return_value = 'recovered'
    assert llm.complete('prompt', 'system').provider == 'gemini'
    assert generate.call_count == 2


def test_single_provider_retries_connection_failure(monkeypatch):
    llm = client()
    fallback = Mock(side_effect=[ConnectionResetError(10054, 'private'), 'recovered'])
    monkeypatch.setattr(llm, '_gemini', fallback)
    monkeypatch.setattr(llm_client.time, 'sleep', Mock())
    assert llm.complete('prompt', 'system').text == 'recovered'
    assert fallback.call_count == 2


def test_retry_budget_is_bounded(monkeypatch):
    llm = client()
    fallback = Mock(side_effect=http_error(504))
    monkeypatch.setattr(llm, '_gemini', fallback)
    monkeypatch.setattr(llm_client.time, 'sleep', Mock())
    with pytest.raises(LLMUnavailable, match='HTTP 504: request timed out'):
        llm.complete('prompt', 'system')
    assert fallback.call_count == 2
