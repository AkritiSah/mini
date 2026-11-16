from unittest.mock import Mock
import pytest
from src.guardrails.input_guardrail import in_scope
from src.guardrails.output_guardrail import validate_answer
from src.translation.translator import detect_language, Translator
from src.llm.llm_client import LLMClient, LLMUnavailable
from src.settings import Settings


def test_scope_and_followups():
    assert in_scope('How can I make compost?', [])
    assert not in_scope('Who is a famous actor?', [])
    assert not in_scope('Write Python code about farming', [])
    assert in_scope('How much should I use?', [{'role': 'user', 'content': 'How to prepare compost?'}])
    assert in_scope('How much should I use?', [{'role': 'user', 'content': 'अदुवा खेती कसरी गर्ने?'}])
    assert in_scope('How to prune mandarin oranges?', [])


def test_language_and_translation_controls():
    assert detect_language('अदुवा खेती कसरी गर्ने?') == 'ne'
    assert detect_language('tomato kheti kasari garne') == 'ne-Latn'
    translator = Translator(Mock(), {'enabled': True, 'normalize_to_english': True, 'translate_documents': False})
    with pytest.raises(ValueError, match='Enable translation'):
        translator.normalize('अदुवा खेती', document=True)


def test_citations_and_language():
    assert validate_answer('Use compost [1]', [{}], 'en')[0]
    assert not validate_answer('Use compost [2]', [{}], 'en')[0]
    assert not validate_answer('Use compost', [{}], 'en')[0]
    assert not validate_answer('Use compost [1]', [{}], 'ne')[0]


def test_claude_first_gemini_fallback(monkeypatch):
    settings = Settings(_env_file=None, anthropic_api_key='test', anthropic_model='test-model', gemini_api_key='test')
    llm = LLMClient(settings, {'temperature': .2, 'max_output_tokens': 500})
    claude, gemini = Mock(return_value='primary'), Mock(return_value='fallback')
    monkeypatch.setattr(llm, '_claude', claude); monkeypatch.setattr(llm, '_gemini', gemini)
    assert llm.complete('prompt', 'system').provider == 'anthropic'
    gemini.assert_not_called()
    claude.side_effect = RuntimeError('private-key')
    result = llm.complete('prompt', 'system')
    assert result.provider == 'gemini' and result.model == 'gemini-3.6-flash'
    gemini.assert_called_with('prompt', 'system', 500)
    gemini.return_value = ''
    with pytest.raises(LLMUnavailable):
        llm.complete('prompt', 'system')


def test_gemini_sdk_preserves_prompt_and_config(monkeypatch):
    from google import genai
    from unittest.mock import MagicMock
    settings = Settings(_env_file=None, gemini_api_key='test')
    constructor = MagicMock()
    client = constructor.return_value.__enter__.return_value
    client.models.generate_content.return_value.text = 'answer'
    monkeypatch.setattr(genai, 'Client', constructor)
    llm = LLMClient(settings, {'temperature': .2, 'max_output_tokens': 500,
                              'timeout_seconds': 60, 'gemini_thinking_level': 'minimal'})
    assert llm._gemini('question and evidence', 'grounding rules', 200) == 'answer'
    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs['model'] == 'gemini-3.6-flash'
    assert kwargs['contents'] == 'question and evidence'
    assert kwargs['config'].system_instruction == 'grounding rules'
    assert kwargs['config'].max_output_tokens == 200
    assert kwargs['config'].thinking_config.thinking_level.value == 'MINIMAL'


def test_real_anthropic_sdk_request_serialization(monkeypatch):
    import anthropic
    import json
    try:
        import httpx2 as transport_module
    except ImportError:
        import httpx as transport_module
    original = anthropic.Anthropic
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return transport_module.Response(200, json={
            'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': 'test-model',
            'content': [{'type': 'text', 'text': 'grounded answer'}],
            'stop_reason': 'end_turn', 'stop_sequence': None,
            'usage': {'input_tokens': 1, 'output_tokens': 1}})

    def client_factory(**kwargs):
        return original(**kwargs, http_client=transport_module.Client(
            transport=transport_module.MockTransport(respond)))

    monkeypatch.setattr(anthropic, 'Anthropic', client_factory)
    settings = Settings(_env_file=None, anthropic_api_key='test', anthropic_model='test-model')
    llm = LLMClient(settings, {'temperature': .2})
    assert llm._claude('evidence and question', 'grounding instructions', 200) == 'grounded answer'
    assert requests[0]['messages'] == [{'role': 'user', 'content': 'evidence and question'}]
    assert requests[0]['system'] == 'grounding instructions'
    assert requests[0]['max_tokens'] == 200
