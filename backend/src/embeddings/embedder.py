from threading import Lock
import numpy as np
from src.settings import ROOT


class Embedder:
    def __init__(self, model_name):
        self.model_name = model_name
        self.model = None
        self.lock = Lock()

    def encode(self, texts):
        with self.lock:
            if self.model is None:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name, device='cpu', trust_remote_code=False,
                                                cache_folder=str(ROOT / '.runtime' / 'models'))
            return np.asarray(self.model.encode(texts, normalize_embeddings=True,
                show_progress_bar=False, batch_size=16), dtype='float32')
