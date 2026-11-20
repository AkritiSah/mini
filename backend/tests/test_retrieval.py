import pytest
from src.retrieval.hybrid_retriever import rrf
from src.retrieval.bm25_retriever import retrieve
from src.vectordb.vector_store import VectorStore
from conftest import FixtureEmbedder


def test_rrf_and_tiny_corpus_bm25():
    assert rrf([[('a', 9), ('b', 8)], [('b', 3), ('c', 2)]])[0][0] == 'b'
    chunks = [{'_id': 'g', 'retrieval_text_en': 'organic ginger compost'}]
    assert retrieve('ginger', chunks, 10)[0][0] == 'g'
    assert retrieve('quantum physics', chunks, 10) == []


def test_frequent_terms_rank_full_match_above_partial_match():
    chunks = [
        {'_id': 'ginger', 'retrieval_text_en': 'organic ginger compost'},
        {'_id': 'rice', 'retrieval_text_en': 'organic rice compost'},
    ]
    assert retrieve('organic ginger compost', chunks, 10)[0][0] == 'ginger'


def test_document_metadata_is_searchable():
    chunks = [
        {'_id': 'g', 'title': 'Ginger manual', 'filename': 'd7_Vermicomposting.pdf',
         'section': 'Soil preparation', 'retrieval_text_en': 'Apply mature compost before planting.'},
        {'_id': 'r', 'title': 'Rice manual', 'retrieval_text_en': 'Irrigate the field.'},
    ]
    assert retrieve('ginger manual', chunks, 10)[0][0] == 'g'
    assert retrieve('vermicomposting', chunks, 10)[0][0] == 'g'
    assert retrieve('soil preparation', chunks, 10)[0][0] == 'g'


def test_vector_persistence_deletion_and_corruption(tmp_path):
    embedder = FixtureEmbedder()
    store = VectorStore(tmp_path, embedder)
    chunks = [{'_id': 'g', 'retrieval_text_en': 'ginger compost'}, {'_id': 'r', 'retrieval_text_en': 'rice irrigation'}]
    store.ensure(chunks)
    assert store.search('ginger compost', 1)[0][0] == 'g'
    calls = embedder.calls
    restored = VectorStore(tmp_path, embedder)
    restored.ensure(chunks)
    assert embedder.calls == calls
    restored.ensure(chunks[:1])
    assert embedder.calls == calls and restored.index.ntotal == 1
    next(tmp_path.glob('*.faiss')).write_bytes(b'corrupt')
    recovered = VectorStore(tmp_path, embedder)
    recovered.ensure(chunks)
    assert recovered.index.ntotal == 2


def test_failed_commit_keeps_previous_snapshot(tmp_path, monkeypatch):
    import src.vectordb.vector_store as module
    store = VectorStore(tmp_path, FixtureEmbedder())
    original = [{'_id': 'a', 'retrieval_text_en': 'ginger compost'}]
    store.ensure(original)
    def fail(*args):
        raise OSError('Disk full')
    monkeypatch.setattr(module, 'atomic_json', fail)
    with pytest.raises(OSError):
        store.ensure(original + [{'_id': 'b', 'retrieval_text_en': 'rice'}])
    assert store.index.ntotal == VectorStore(tmp_path, FixtureEmbedder()).index.ntotal == 1


def test_precomputed_vectors_are_committed_without_repeating_inference(tmp_path):
    from src.vectordb.vector_store import signatures
    embedder = FixtureEmbedder()
    store = VectorStore(tmp_path, embedder)
    chunks = [{'_id': 'g', 'retrieval_text_en': 'ginger compost'}]
    encoded = embedder.encode([chunks[0]['retrieval_text_en']])
    store.ensure(chunks, precomputed=dict(zip(signatures(chunks), encoded)))
    assert embedder.calls == 1
    assert store.search('ginger compost', 1)[0][0] == 'g'
