import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
import faiss
import numpy as np
from src.utils.helpers import atomic_json


def signatures(chunks):
    return [(c['_id'], hashlib.sha256(c['retrieval_text_en'].encode()).hexdigest()) for c in chunks]


class VectorStore:
    """Single-writer normalized inner-product FAISS with an atomic manifest commit."""
    def __init__(self, path: Path, embedder):
        self.path, self.embedder = path, embedder
        self.path.mkdir(parents=True, exist_ok=True)
        self.index, self.entries = None, []
        self.load()

    def load(self):
        manifest = self.path / 'manifest.json'
        if not manifest.exists():
            return
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
            if data['model'] != self.embedder.model_name:
                return
            filename = data['index_file']
            if Path(filename).name != filename:
                raise ValueError('Invalid index filename')
            blob = (self.path / filename).read_bytes()
            if hashlib.sha256(blob).hexdigest() != data['checksum']:
                raise ValueError('Index checksum mismatch')
            index = faiss.deserialize_index(np.frombuffer(blob, dtype='uint8'))
            entries = [tuple(item) for item in data['entries']]
            if index.ntotal != len(entries):
                raise ValueError('Index mapping mismatch')
            self.index, self.entries = index, entries
        except (OSError, ValueError, KeyError, RuntimeError):
            # MongoDB remains authoritative; ensure() rebuilds a corrupt snapshot.
            self.index, self.entries = None, []

    def ensure(self, chunks, force=False):
        desired = signatures(chunks)
        if desired == self.entries and not force:
            return
        cached = {entry: self.index.reconstruct(i) for i, entry in enumerate(self.entries)} if self.index is not None and not force else {}
        missing = [i for i, entry in enumerate(desired) if entry not in cached]
        new_vectors = self.embedder.encode([chunks[i]['retrieval_text_en'] for i in missing]) if missing else []
        additions = dict(zip((desired[i] for i in missing), new_vectors))
        vectors = [cached[entry] if entry in cached else additions[entry] for entry in desired]
        dimension = len(vectors[0]) if vectors else (self.index.d if self.index is not None else 768)
        index = faiss.IndexFlatIP(dimension)
        if vectors:
            index.add(np.ascontiguousarray(vectors, dtype='float32'))
        generation = uuid4().hex
        filename = generation + '.faiss'
        blob = faiss.serialize_index(index).tobytes()
        target = self.path / filename
        with target.open('wb') as stream:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_json(self.path / 'manifest.json', {'index_file': filename,
            'checksum': hashlib.sha256(blob).hexdigest(), 'entries': desired,
            'model': self.embedder.model_name, 'dimension': dimension})
        self.index, self.entries = index, desired
        # The manifest commit is complete. Old generations are no longer referenced.
        for previous in self.path.glob('*.faiss'):
            if previous != target:
                previous.unlink(missing_ok=True)

    def search(self, query, top_k):
        if self.index is None or self.index.ntotal == 0:
            return []
        vector = self.embedder.encode([query])
        scores, positions = self.index.search(vector, min(top_k, self.index.ntotal))
        return [(self.entries[int(position)][0], float(score))
                for position, score in zip(positions[0], scores[0]) if position >= 0]
