"""Download configured MPNet and reranker weights without ingesting documents."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from src.settings import Settings
from src.embeddings.embedder import Embedder
from src.retrieval.reranker import Reranker

if __name__ == '__main__':
    settings = Settings()
    vector = Embedder(settings.embedding_model).encode(['Organic farming in Sikkim'])
    print(f'MPNet ready: {vector.shape[1]} dimensions')
    result = Reranker(settings.reranker_model).rank('organic farming', [{'retrieval_text_en': 'Organic farming uses compost.'}], 1)
    print(f'Reranker ready: {len(result)} passage scored')
