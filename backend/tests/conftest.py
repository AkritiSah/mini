import hashlib
import re
import mongomock
import numpy as np
import pytest
from fastapi.testclient import TestClient
from src.application import Application
from src.llm.llm_client import Completion
from src.settings import Settings, load_config


class FixtureEmbedder:
    """Test-only vectors. Production always uses MPNet."""
    model_name = 'deterministic-test-only'
    model = True

    def __init__(self):
        self.calls = 0

    def encode(self, texts):
        self.calls += 1
        vectors = np.zeros((len(texts), 32), dtype='float32')
        for i, text in enumerate(texts):
            for word in re.findall(r'\w+', text.lower()):
                vectors[i, int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % 32] += 1
            norm = np.linalg.norm(vectors[i])
            if norm:
                vectors[i] /= norm
        return vectors


class FixtureLLM:
    def initialize(self):
        pass

    def close(self):
        pass

    def complete(self, prompt, system, max_tokens=None):
        if system.startswith('Audit'):
            answer = '{"supported": true}'
        elif system.startswith(('Translate', 'Rewrite')):
            answer = 'How do I grow organic ginger in Sikkim?'
        else:
            import json
            language = json.loads(prompt).get('response_language')
            answer = {'ne': 'अदुवा खेतीका लागि कम्पोस्ट प्रयोग गर्नुहोस्। [1]',
                      'ne-Latn': 'Aduwa kheti ma compost prayog garnuhos. [1]'}.get(language,
                      'Use compost for organic ginger cultivation. [1]')
        return Completion(answer, 'test-fixture', 'offline')


@pytest.fixture
def application(tmp_path, monkeypatch):
    from src.api import routes
    from src.ingestion import ingestion_service
    monkeypatch.setattr(routes, 'ROOT', tmp_path)
    monkeypatch.setattr(ingestion_service, 'ROOT', tmp_path)
    settings = Settings(_env_file=None, faiss_index_path=str(tmp_path / 'indices'))
    config = load_config()
    config['retrieval']['rerank_enabled'] = False
    return Application(settings, config, database=mongomock.MongoClient().krishi,
                       embedder=FixtureEmbedder(), llm=FixtureLLM())


@pytest.fixture
def client(application):
    from main import create_app
    with TestClient(create_app(application)) as client:
        yield client
