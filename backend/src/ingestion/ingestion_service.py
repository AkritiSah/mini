import logging
from pathlib import Path
from uuid import uuid4
from src.chunking.chunker import chunk_sections
from src.ingestion.loader import load_sections
from src.llm.llm_client import LLMUnavailable
from src.translation.translator import detect_language
from src.settings import ROOT
from src.utils.helpers import atomic_json, now

logger = logging.getLogger('krishi')


class IngestionService:
    def __init__(self, app):
        self.app = app

    def update_job(self, job_id, status, progress, **extra):
        self.app.repo.db.ingestion_jobs.update_one({'_id': job_id}, {'$set': {
            'status': status, 'progress': progress, **extra}})

    def queue(self, document_id):
        job_id = uuid4().hex
        self.app.repo.db.documents.update_one({'_id': document_id}, {'$set': {'status': 'queued', 'error': None}})
        self.app.repo.db.ingestion_jobs.insert_one({'_id': job_id, 'document_id': document_id,
            'status': 'queued', 'progress': 0, 'started_at': now(), 'completed_at': None, 'error': None})
        return job_id

    def process(self, document_id, job_id):
        app = self.app
        with app.lock:
            document = app.repo.document(document_id)
            if not document:
                return
            try:
                app.repo.db.documents.update_one({'_id': document_id}, {'$set': {'status': 'processing'}})
                self.update_job(job_id, 'extracting', 10)
                sections = load_sections(Path(document['local_path']), app.settings.soffice_path)
                self.update_job(job_id, 'chunking', 30)
                chunks = chunk_sections(sections, document, app.config['chunking'])
                if not chunks:
                    raise ValueError('No readable chunks were extracted.')
                self.update_job(job_id, 'normalizing', 40)
                for chunk in chunks:
                    normalized, language = app.translator.normalize(chunk['original_text'], document=True)
                    chunk['retrieval_text_en'], chunk['language'] = normalized, language
                atomic_json(ROOT / 'data' / 'processed' / (document_id + '.json'), chunks)
                self.update_job(job_id, 'embedding', 65)
                # A processing document is not searchable. Replace its chunks before the new manifest commit.
                app.repo.db.chunks.delete_many({'document_id': document_id})
                app.repo.db.chunks.insert_many(chunks)
                indexed = app.repo.searchable_chunks()
                app.vectors.ensure(sorted(indexed + chunks, key=lambda c: c['_id']))
                app.repo.db.documents.update_one({'_id': document_id}, {'$set': {
                    'status': 'indexed', 'chunk_count': len(chunks), 'error': None,
                    'language': detect_language('\n'.join(s.text for s in sections)),
                    'indexed_at': now(), 'embedding_model': app.settings.embedding_model}})
                self.update_job(job_id, 'completed', 100, completed_at=now())
                logger.info('document=%s ingestion_completed chunks=%s', document_id, len(chunks))
            except Exception as error:
                app.repo.db.chunks.delete_many({'document_id': document_id})
                # Display actionable parser/config errors; never publish SDK error bodies.
                message = str(error)[:500] if isinstance(error, (ValueError, LLMUnavailable)) else 'Document processing failed. Check parser dependencies, model downloads, and local storage; then reindex.'
                app.repo.db.documents.update_one({'_id': document_id}, {'$set': {
                    'status': 'failed', 'error': message, 'chunk_count': 0}})
                self.update_job(job_id, 'failed', 100, error=message, completed_at=now())
                logger.error('document=%s ingestion_failed error_type=%s', document_id, type(error).__name__)

    def delete(self, document_id):
        app = self.app
        with app.lock:
            document = app.repo.document(document_id)
            if not document:
                return False
            app.repo.db.documents.update_one({'_id': document_id}, {'$set': {'status': 'deleting'}})
            app.vectors.ensure(app.repo.searchable_chunks())
            app.repo.db.chunks.delete_many({'document_id': document_id})
            Path(document['local_path']).unlink(missing_ok=True)
            (ROOT / 'data' / 'processed' / (document_id + '.json')).unlink(missing_ok=True)
            app.repo.db.ingestion_jobs.delete_many({'document_id': document_id})
            app.repo.db.documents.delete_one({'_id': document_id})
            return True
