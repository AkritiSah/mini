from pymongo import MongoClient


def connect(settings):
    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=2000,
                         connectTimeoutMS=2000, socketTimeoutMS=10000)
    return client, client[settings.mongodb_database]
