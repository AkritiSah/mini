from collections import defaultdict
from . import bm25_retriever, dense_retriever


def rrf(rankings, k=60):
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, (chunk_id, _) in enumerate(ranking, 1):
            scores[chunk_id] += 1 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


class HybridRetriever:
    def __init__(self, vectors, reranker, config):
        self.vectors, self.reranker, self.config = vectors, reranker, config

    def retrieve(self, query, chunks, filters=None):
        config = self.config
        candidates = [chunk for chunk in chunks if all(
            chunk.get(key) == value for key, value in (filters or {}).items() if value)]
        by_id = {chunk['_id']: chunk for chunk in candidates}
        sparse = bm25_retriever.retrieve(query, candidates, config['bm25_top_k']) if config['mode'] != 'dense' else []
        dense = dense_retriever.retrieve(query, self.vectors, config['faiss_top_k']) if config['mode'] != 'bm25' else []
        dense = [(key, score) for key, score in dense if key in by_id and score >= config['min_dense_score']]
        rankings = [sparse] if config['mode'] == 'bm25' else [dense] if config['mode'] == 'dense' else [sparse, dense]
        fused = rrf(rankings, config['rrf_k'])
        results = [{**by_id[key], 'retrieval_score': score} for key, score in fused[:config['rerank_input_limit']]]
        if config['rerank_enabled'] and results:
            results = self.reranker.rank(query, results, config['rerank_top_k'])
        return results[:config['context_top_k']]
