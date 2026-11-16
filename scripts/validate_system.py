"""Real MongoDB/MPNet/FAISS/RAG check using an isolated temporary database.

Run after prefetch_models.py and downloading the official validation PDF:
    .venv/Scripts/python scripts/validate_system.py [--live]
--live makes real paid generation/translation/audit requests.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('HF_HUB_OFFLINE', '1')
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from main import create_app
from src.application import Application
from src.api import routes
from src.ingestion import ingestion_service
from src.settings import Settings, load_config


def main():
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--live', action='store_true')
    live = arguments.parse_args().live
    runtime = ROOT / '.runtime'
    sample = runtime / 'icar-ginger-validation.pdf'
    if not sample.exists():
        raise SystemExit('Download the official validation PDF into .runtime/icar-ginger-validation.pdf first.')
    settings = Settings()
    database_name = 'krishi_mitra_validation_' + uuid4().hex
    mongo = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=1000)
    owned_process = None
    report = {'database': database_name, 'live_llm': live, 'checks': []}

    def passed(message):
        report['checks'].append(message)
        print('PASS: ' + message, flush=True)

    try:
        try:
            mongo.admin.command('ping')
        except PyMongoError:
            binaries = list((runtime / 'mongodb').rglob('mongod.exe'))
            if not binaries:
                raise SystemExit('Start MongoDB first, or run scripts/setup_mongo.ps1.')
            data_path = runtime / 'mongo-validation-data'
            data_path.mkdir(exist_ok=True)
            owned_process = subprocess.Popen([str(binaries[0]), '--dbpath', str(data_path),
                '--bind_ip', '127.0.0.1', '--port', '27017', '--logpath', str(runtime / 'mongo-validation.log')],
                creationflags=subprocess.CREATE_NO_WINDOW)
            for _ in range(40):
                try:
                    mongo.admin.command('ping')
                    break
                except PyMongoError:
                    time.sleep(.5)
            else:
                raise SystemExit('Validation MongoDB did not start.')
        passed('Real MongoDB connection')
        with tempfile.TemporaryDirectory(prefix='system-check-', dir=runtime) as temporary:
            temporary_root = Path(temporary).resolve()
            assert temporary_root.is_relative_to(runtime.resolve())
            routes.ROOT = ingestion_service.ROOT = temporary_root
            settings = settings.model_copy(update={'mongodb_database': database_name,
                                                  'faiss_index_path': str(temporary_root / 'indices')})
            app = Application(settings, load_config())
            with TestClient(create_app(app)) as client:
                assert client.get('/api/health').status_code == 200
                response = client.post('/api/documents/upload', files={'file': ('ICAR-Ginger.pdf', sample.read_bytes(), 'application/pdf')},
                    data={'title': 'ICAR-IISR Ginger pamphlet (validation only)',
                          'source_organization': 'ICAR-Indian Institute of Spices Research',
                          'source_url': 'https://www.spices.res.in/storage/app/public/pdfs/GINGER/2ENG.pdf',
                          'crop': 'ginger'})
                assert response.status_code == 202, response.text
                document_id, job_id = response.json()['document_id'], response.json()['job_id']
                job = client.get('/api/jobs/' + job_id).json()
                assert job['status'] == 'completed', job
                records = client.get('/api/documents').json()
                assert records['chunk_count'] > 0 and app.vectors.index.d == 768
                passed(f'Official PDF -> original file + MongoDB chunks + {app.vectors.index.ntotal} MPNet/FAISS vectors')
                with app.lock:
                    selected = app.retriever.retrieve('suitable soil conditions for ginger cultivation', app.sync_index())
                assert selected and 'rerank_score' in selected[0]
                passed('Real hybrid retrieval and cross-encoder reranking')
                unrelated = client.post('/api/chat', json={'question': 'Write Python code'}).json()
                assert unrelated['evidence_status'] == 'out_of_scope'
                passed('Unrelated query refused')
                if live:
                    for question, language in [
                        ('Briefly describe suitable soil conditions for ginger cultivation.', 'en'),
                        ('अदुवा खेतीका लागि कस्तो माटो चाहिन्छ? छोटो उत्तर दिनुहोस्।', 'ne'),
                        ('Aduwa kheti ko lagi kasto mato chahinchha? Chhoto uttar dinuhos.', 'ne-Latn')]:
                        answer = client.post('/api/chat', json={'question': question})
                        assert answer.status_code == 200, answer.text
                        result = answer.json()
                        assert result['detected_language'] == language, result
                        assert result['evidence_status'] == 'supported' and result['citations'], result
                        report.setdefault('providers', []).append(result['metadata']['provider'])
                        passed(f'Live {language} answer, traceable citations, and evidence audit ({result["metadata"]["provider"]})')
                rebuilt = client.post('/api/documents/' + document_id + '/reindex')
                assert rebuilt.status_code == 202
                passed('Document reindex')
            restored = Application(settings, load_config())
            with TestClient(create_app(restored)) as client:
                assert restored.vectors.index.ntotal == records['chunk_count']
                assert restored.embedder.model is None
                passed('Backend restart reuses persisted vectors without loading MPNet')
                assert client.delete('/api/documents/' + document_id).status_code == 200
                assert restored.vectors.index.ntotal == 0
                assert client.get('/api/documents').json()['document_count'] == 0
                empty = client.post('/api/chat', json={'question': 'How to cultivate organic ginger?'}).json()
                assert empty['evidence_status'] == 'insufficient'
                passed('Deletion removes source/chunks/vectors; missing evidence is reported')
    finally:
        # This UUID database was created solely by this invocation. Never drop user data.
        assert database_name.startswith('krishi_mitra_validation_')
        try:
            mongo.drop_database(database_name)
        finally:
            if owned_process:
                try:
                    mongo.admin.command({'shutdown': 1})
                except PyMongoError:
                    pass
                try:
                    owned_process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    owned_process.terminate()
            mongo.close()
        (runtime / 'system-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
