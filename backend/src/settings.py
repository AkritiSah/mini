from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND / '.env', extra='ignore')
    anthropic_api_key: str = ''
    anthropic_model: str = ''
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-3.6-flash'
    mongodb_uri: str = 'mongodb://127.0.0.1:27017'
    mongodb_database: str = 'krishi_mitra'
    embedding_model: str = 'sentence-transformers/all-mpnet-base-v2'
    reranker_model: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
    faiss_index_path: str = '../data/indices'
    max_upload_mb: int = Field(default=50, ge=1, le=500)
    soffice_path: str = ''

    @property
    def index_path(self):
        return (BACKEND / self.faiss_index_path).resolve()

    @property
    def llm_ready(self):
        return bool((self.anthropic_api_key and self.anthropic_model) or self.gemini_api_key)


def load_config():
    with (BACKEND / 'config.yaml').open(encoding='utf-8') as handle:
        config = yaml.safe_load(handle)
    chunk = config['chunking']
    if not 0 <= chunk['overlap_words'] < chunk['target_words'] <= chunk['max_words']:
        raise ValueError('Require overlap_words < target_words <= max_words.')
    retrieval = config['retrieval']
    if retrieval['mode'] not in {'bm25', 'dense', 'hybrid'}:
        raise ValueError('Unknown retrieval mode.')
    for key in ('bm25_top_k', 'faiss_top_k', 'rerank_input_limit', 'rerank_top_k', 'context_top_k'):
        if retrieval[key] < 1:
            raise ValueError(f'{key} must be positive.')
    return config
