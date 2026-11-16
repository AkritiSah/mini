from threading import Lock
from src.settings import ROOT


class Reranker:
    def __init__(self, model_name):
        self.model_name, self.model = model_name, None
        self.lock = Lock()

    def rank(self, query, chunks, top_k):
        if not chunks:
            return []
        with self.lock:
            if self.model is None:
                from sentence_transformers import CrossEncoder
                self.model = CrossEncoder(self.model_name, device='cpu', trust_remote_code=False,
                                          cache_folder=str(ROOT / '.runtime' / 'models'))
            scores = self.model.predict([(query, c['retrieval_text_en']) for c in chunks],
                                        show_progress_bar=False, batch_size=16)
        scored = [{**chunk, 'rerank_score': float(score)} for chunk, score in zip(chunks, scores)]
        return sorted(scored, key=lambda c: c['rerank_score'], reverse=True)[:top_k]
