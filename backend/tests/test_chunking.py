from src.chunking.chunker import chunk_sections
from src.ingestion.parsers import Section


def test_bounds_overlap_and_metadata():
    text = ' '.join(f'Sentence {i} has five words.' for i in range(30))
    chunks = chunk_sections([Section(text, 4, 'Ginger')], {'_id': 'd', 'title': 'Fixture'},
                            {'target_words': 20, 'max_words': 25, 'overlap_words': 5})
    assert len(chunks) > 1
    assert all(len(c['original_text'].split()) <= 25 and c['page'] == 4 for c in chunks)
    assert chunks[0]['original_text'].splitlines()[-1] == chunks[1]['original_text'].splitlines()[0]


def test_small_table_and_heading_preserved():
    chunks = chunk_sections([Section('# Ginger\n\nCrop | Rate\nGinger | 5 kg')], {'_id': 'd'},
                            {'target_words': 50, 'max_words': 60, 'overlap_words': 5})
    assert len(chunks) == 1 and 'Crop | Rate\nGinger | 5 kg' in chunks[0]['original_text']
    assert chunks[0]['section'] == 'Ginger'
