from unittest.mock import Mock

from src.llm.llm_client import Completion
from src.translation import translator


def test_document_translation_is_paced_but_queries_and_english_are_not(monkeypatch):
    clock = [100.0]
    sleep = Mock(side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(translator.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(translator.time, 'sleep', sleep)
    llm = Mock()
    llm.complete.return_value = Completion('Grow potatoes in well-drained soil.', 'fixture', 'offline')
    service = translator.Translator(llm, {'enabled': True, 'normalize_to_english': True,
        'translate_documents': True, 'document_request_interval_seconds': 12})
    service.normalize('आलु खेती', document=True)
    service.normalize('आलु खेती कसरी गर्ने?')
    service.normalize('Organic potato cultivation.', document=True)
    sleep.assert_not_called()
    service.normalize('आलु खेतीमा बीउ छान्ने', document=True)
    sleep.assert_called_once_with(12)
    assert llm.complete.call_count == 3
