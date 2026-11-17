import logging
from threading import RLock
from src.database.mongo_client import connect
from src.database.repositories import Repository
from src.embeddings.embedder import Embedder
from src.ingestion.ingestion_service import IngestionService
from src.llm.llm_client import LLMClient
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.reranker import Reranker
from src.translation.translator import Translator
from src.utils.helpers import now
from src.vectordb.vector_store import VectorStore

logger = logging.getLogger('krishi')


class Application:
    def __init__(self, settings, config, *, database=None, embedder=None, llm=None):
        self.settings, self.config, self.lock = settings, config, RLock()
        self.client = None
        if database is None:
            self.client, database = connect(settings)
        self.repo = Repository(database)
        self.embedder = embedder or Embedder(settings.embedding_model)
        self.vectors = VectorStore(settings.index_path, self.embedder)
        self.llm = llm or LLMClient(settings, config['generation'])
        self.translator = Translator(self.llm, config['translation'])
        self.reranker = Reranker(settings.reranker_model)
        self.retriever = HybridRetriever(self.vectors, self.reranker, config['retrieval'])
        self.ingestion = IngestionService(self)
        self.initialized = False
        self.index_ready = False

    def initialize(self):
        with self.lock:
            if self.initialized:
                return
            self.llm.initialize()
            self.repo.db.command('ping')
            self.repo.initialize()
            # A stopped ingestion cannot be reported as indexed on restart.
            interrupted = self.repo.db.documents.find({'status': {'$in': ['queued', 'processing']}})
            for document in interrupted:
                self.repo.db.chunks.delete_many({'document_id': document['_id']})
                self.repo.db.documents.update_one({'_id': document['_id']}, {'$set': {
                    'status': 'failed', 'chunk_count': 0, 'error': 'Processing was interrupted. Reindex this document.'}})
            self.repo.db.ingestion_jobs.update_many({'status': {'$nin': ['completed', 'failed']}},
                {'$set': {'status': 'failed', 'error': 'Backend restarted. Reindex the document.', 'completed_at': now()}})
            for document in self.repo.db.documents.find({'status': 'deleting'}):
                self.ingestion.delete(document['_id'])
            self.initialized = True
            try:
                self.sync_index()
            except Exception:
                logger.error('index_recovery_failed; retry with rebuild_index.py or a retrieval request')

    def sync_index(self):
        self.index_ready = False
        chunks = self.repo.searchable_chunks()
        self.vectors.ensure(chunks)
        self.index_ready = True
        return chunks

    def close(self):
        try:
            self.llm.close()
        finally:
            if self.client is not None:
                self.client.close()
