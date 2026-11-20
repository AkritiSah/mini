import logging
import hashlib
import json
from pathlib import Path
from threading import Lock
from uuid import uuid4
from src.chunking.chunker import chunk_sections
from src.ingestion.loader import load_sections
from src.llm.llm_client import LLMUnavailable
from src.translation.translator import detect_language, TRANSLATION_SYSTEM
from src.settings import ROOT
from src.utils.helpers import atomic_json, now
from src.vectordb.vector_store import signatures

logger = logging.getLogger('krishi')


class IngestionService:
    def __init__(self, app):
        self.app = app
        self.parser_lock = Lock()

    def update_job(self, job_id, status, progress, **extra):
        self.app.repo.db.ingestion_jobs.update_one({'_id': job_id}, {'$set': {
            'status': status, 'progress': progress, **extra}})

    def queue(self, document_id):
        job_id = uuid4().hex
        self.app.repo.db.documents.update_one({'_id': document_id}, {'$set': {'status': 'queued', 'error': None}})
        self.app.repo.db.ingestion_jobs.insert_one({'_id': job_id, 'document_id': document_id,
            'status': 'queued', 'progress': 0, 'started_at': now(), 'completed_at': None, 'error': None})
        return job_id

    def normalize_chunk(self, document_id, text):
        app = self.app
        # Chunk IDs are regenerated on reindex. Cache by source text and translation
        # settings so retries/restarts reuse only compatible, successful translations.
        key = hashlib.sha256(json.dumps([document_id, text, app.settings.gemini_model,
            TRANSLATION_SYSTEM, app.config['translation']], sort_keys=True).encode()).hexdigest()
        cached = app.repo.db.translation_cache.find_one({'_id': key})
        if cached:
            return cached['text'], cached['language']
        normalized, language = app.translator.normalize(text, document=True)
        if language != 'en' and normalized != text:
            with app.lock:
                current = app.repo.document(document_id)
                if current and current['status'] == 'processing':
                    app.repo.db.translation_cache.update_one({'_id': key}, {'$set': {
                        'document_id': document_id, 'text': normalized, 'language': language}}, upsert=True)
        return normalized, language

    def process(self, document_id, job_id):
        app = self.app
        with app.lock:
            document = app.repo.document(document_id)
            if not document:
                return
            app.repo.db.documents.update_one({'_id': document_id}, {'$set': {'status': 'processing'}})
        try:
            # Parsing, translation, and model inference can take minutes. Existing
            # indexed sources remain available while the new document is prepared.
            self.update_job(job_id, 'extracting', 10)
            def on_page(completed, total, used_ocr):
                self.update_job(job_id, 'ocr' if used_ocr else 'extracting',
                                10 + int(18 * completed / max(total, 1)),
                                processed_pages=completed, total_pages=total)
            with self.parser_lock:
                sections = load_sections(Path(document['local_path']), app.settings.soffice_path,
                                         app.config.get('ocr', {}), on_page)
            self.update_job(job_id, 'chunking', 30)
            chunks = chunk_sections(sections, document, app.config['chunking'])
            if not chunks:
                raise ValueError('No readable chunks were extracted.')
            self.update_job(job_id, 'normalizing', 40)
            for position, chunk in enumerate(chunks, 1):
                normalized, language = self.normalize_chunk(document_id, chunk['original_text'])
                chunk['retrieval_text_en'], chunk['language'] = normalized, language
                self.update_job(job_id, 'normalizing', 40 + int(24 * position / len(chunks)),
                                normalized_chunks=position, total_chunks=len(chunks))
            self.update_job(job_id, 'embedding', 65)
            encoded = app.embedder.encode([chunk['retrieval_text_en'] for chunk in chunks])
            precomputed = dict(zip(signatures(chunks), encoded))
            with app.lock:
                # A user may delete a document while it is being prepared.
                current = app.repo.document(document_id)
                if not current or current['status'] != 'processing':
                    return
                atomic_json(ROOT / 'data' / 'processed' / (document_id + '.json'), chunks)
                # A processing document is not searchable. Replace its chunks before the new manifest commit.
                app.repo.db.chunks.delete_many({'document_id': document_id})
                app.repo.db.chunks.insert_many(chunks)
                indexed = app.repo.searchable_chunks()
                app.vectors.ensure(sorted(indexed + chunks, key=lambda c: c['_id']), precomputed=precomputed)
                app.repo.db.documents.update_one({'_id': document_id}, {'$set': {
                    'status': 'indexed', 'chunk_count': len(chunks), 'error': None,
                    'language': detect_language('\n'.join(s.text for s in sections), document=True),
                    'indexed_at': now(), 'embedding_model': app.settings.embedding_model}})
                self.update_job(job_id, 'completed', 100, completed_at=now())
                logger.info('document=%s ingestion_completed chunks=%s', document_id, len(chunks))
        except Exception as error:
            with app.lock:
                current = app.repo.document(document_id)
                if not current or current['status'] != 'processing':
                    return
                app.repo.db.chunks.delete_many({'document_id': document_id})
                # Display actionable parser/config errors; never publish SDK error bodies.
                message = str(error)[:500] if isinstance(error, (ValueError, LLMUnavailable)) else 'Document processing failed. Check parser dependencies, model downloads, and local storage; then reindex.'
                if isinstance(error, LLMUnavailable):
                    message += ' Completed translations are saved; use Reindex to resume after the provider issue is resolved.'
                app.repo.db.documents.update_one({'_id': document_id}, {'$set': {
                    'status': 'failed', 'error': message, 'chunk_count': 0}})
                job = app.repo.db.ingestion_jobs.find_one({'_id': job_id}) or {}
                self.update_job(job_id, 'failed', job.get('progress', 0), error=message, completed_at=now(),
                                error_category=getattr(error, 'category', None),
                                retry_after_seconds=getattr(error, 'retry_after', None))
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
            app.repo.db.translation_cache.delete_many({'document_id': document_id})
            Path(document['local_path']).unlink(missing_ok=True)
            (ROOT / 'data' / 'processed' / (document_id + '.json')).unlink(missing_ok=True)
            app.repo.db.ingestion_jobs.delete_many({'document_id': document_id})
            app.repo.db.documents.delete_one({'_id': document_id})
            return True
