from pymongo import ASCENDING


class Repository:
    def __init__(self, database):
        self.db = database

    def initialize(self):
        self.db.documents.create_index([('file_hash', ASCENDING)], unique=True)
        self.db.chunks.create_index('document_id')
        self.db.ingestion_jobs.create_index('document_id')

    def document(self, document_id):
        return self.db.documents.find_one({'_id': document_id})

    def documents(self):
        return list(self.db.documents.find().sort('uploaded_at', -1))

    def searchable_chunks(self):
        ids = [doc['_id'] for doc in self.db.documents.find({'status': 'indexed'}, {'_id': 1})]
        return list(self.db.chunks.find({'document_id': {'$in': ids}}).sort('_id', 1))
