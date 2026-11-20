from unittest.mock import Mock
import pytest
from src.guardrails.input_guardrail import in_scope
from src.guardrails.output_guardrail import citation_ids, validate_answer
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


@pytest.mark.parametrize('text', [
    'English farming guidance describes Rishi kheti as a traditional method.',
    'Bali is listed among the locations covered by this English farming report.',
    '(मध्य भारती) Journal of agriculture. This English article discusses organic farming, '
    'soil health, pest management, composting and sustainable crop production.',
    'Ginger (aduwa) cultivation guidance for farmers in Sikkim.',
])
def test_english_document_with_local_names_does_not_require_translation(text):
    llm = Mock()
    translator = Translator(llm, {'enabled': True, 'normalize_to_english': True, 'translate_documents': False})
    assert translator.normalize(text, document=True) == (text, 'en')
    llm.complete.assert_not_called()


def test_romanized_document_still_requires_translation():
    translator = Translator(Mock(), {'enabled': True, 'normalize_to_english': True, 'translate_documents': False})
    with pytest.raises(ValueError, match='Enable translation'):
        translator.normalize('Aduwa kheti kasari garne? Malai biruwa rog chha.', document=True)


def test_citations_and_language():
    assert validate_answer('Use compost [1]', [{}], 'en')[0]
    assert not validate_answer('Use compost [2]', [{}], 'en')[0]
    assert not validate_answer('Use compost', [{}], 'en')[0]
    assert not validate_answer('Use compost [1]', [{}], 'ne')[0]


def test_grouped_citations_are_parsed_and_validated():
    assert citation_ids('Use compost [1, 2]. Mulch [2,3] and rotate crops [4].') == {1, 2, 3, 4}
    assert validate_answer('Use compost [1, 2].', [{}, {}], 'en')[0]
    assert not validate_answer('Use compost [1, 999].', [{}, {}], 'en')[0]


def test_gemini_sdk_preserves_prompt_and_reuses_client(monkeypatch):
    from google import genai
    from unittest.mock import MagicMock
    settings = Settings(_env_file=None, gemini_api_key='test')
    constructor = MagicMock()
    sdk = constructor.return_value
    sdk.models.generate_content.return_value.text = 'answer'
    monkeypatch.setattr(genai, 'Client', constructor)
    llm = LLMClient(settings, {'max_output_tokens': 500,
                              'timeout_seconds': 60, 'gemini_thinking_level': 'minimal'})
    llm.initialize()
    llm.initialize()
    assert llm.complete('question and evidence', 'grounding rules', 200).text == 'answer'
    assert llm.complete('next question', 'grounding rules', 100).provider == 'gemini'
    constructor.assert_called_once()
    sdk.models.get.assert_called_once()
    assert sdk.models.get.call_args.kwargs['config'].http_options.timeout == 10000
    assert sdk.models.generate_content.call_count == 2
    kwargs = sdk.models.generate_content.call_args_list[0].kwargs
    assert kwargs['model'] == 'gemini-3.1-flash-lite'
    assert kwargs['contents'] == 'question and evidence'
    assert kwargs['config'].system_instruction == 'grounding rules'
    assert kwargs['config'].max_output_tokens == 200
    assert kwargs['config'].temperature is None
    assert kwargs['config'].thinking_config.thinking_level.value == 'MINIMAL'
    options = constructor.call_args.kwargs['http_options']
    assert options.timeout == 60000
    assert options.retry_options.attempts == 1
    sdk.close.assert_not_called()
    llm.close()
    llm.close()
    sdk.close.assert_called_once()
    with pytest.raises(LLMUnavailable, match='closed'):
        llm._gemini('question', 'system', 100)


def test_concurrent_startup_only_checks_connection_once(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from google import genai
    from unittest.mock import MagicMock
    constructor = MagicMock()
    monkeypatch.setattr(genai, 'Client', constructor)
    llm = LLMClient(Settings(_env_file=None, gemini_api_key='test'), {})
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: llm.initialize(), range(8)))
    constructor.assert_called_once()
    constructor.return_value.models.get.assert_called_once()
    assert llm.connection_status == 'ready'
    llm.close()


def test_failed_startup_connection_can_recover_without_recreating_client(monkeypatch):
    from google import genai
    from unittest.mock import MagicMock
    constructor = MagicMock()
    sdk = constructor.return_value
    sdk.models.get.side_effect = ConnectionResetError(10054, 'private endpoint')
    sdk.models.generate_content.return_value.text = 'recovered'
    monkeypatch.setattr(genai, 'Client', constructor)
    llm = LLMClient(Settings(_env_file=None, gemini_api_key='test'), {'max_output_tokens': 100})
    llm.initialize()
    assert llm.connection_status == 'unavailable'
    assert llm.complete('prompt', 'system').text == 'recovered'
    llm.initialize()
    assert llm.connection_status == 'ready'
    sdk.models.get.assert_called_once()
    constructor.assert_called_once()
    llm.close()


def test_missing_key_does_not_construct_client(monkeypatch):
    from google import genai
    constructor = Mock()
    monkeypatch.setattr(genai, 'Client', constructor)
    llm = LLMClient(Settings(_env_file=None, gemini_api_key=''), {})
    llm.initialize()
    with pytest.raises(LLMUnavailable, match='GEMINI_API_KEY'):
        llm.complete('prompt', 'system')
    constructor.assert_not_called()
