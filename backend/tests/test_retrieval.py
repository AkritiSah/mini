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
