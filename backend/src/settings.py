from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND / '.env', extra='ignore')
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-3.1-flash-lite'
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
        return bool(self.gemini_api_key and self.gemini_model)


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
    generation = config['generation']
    for key in ('timeout_seconds', 'gemini_timeout_seconds', 'connection_check_timeout_seconds'):
        if generation.get(key, 60) <= 0:
            raise ValueError(f'{key} must be positive.')
    attempts = generation.get('max_provider_attempts', 2)
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError('max_provider_attempts must be an integer from 1 to 3.')
    for key in ('retry_initial_delay_seconds', 'provider_cooldown_seconds',
                'rate_limit_retry_seconds', 'max_retry_wait_seconds'):
        if generation.get(key, 0) < 0:
            raise ValueError(f'{key} cannot be negative.')
    if not 0 <= config['translation'].get('document_request_interval_seconds', 12) <= 60:
        raise ValueError('document_request_interval_seconds must be between 0 and 60.')
    ocr = config.get('ocr', {})
    if type(ocr.get('dpi', 250)) is not int or not 100 <= ocr.get('dpi', 250) <= 400:
        raise ValueError('ocr.dpi must be an integer between 100 and 400.')
    if any(language not in {'eng', 'nep'} for language in ocr.get('languages', 'eng+nep').split('+')):
        raise ValueError('ocr.languages supports eng, nep, or eng+nep.')
    return config
