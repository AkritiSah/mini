def retrieve(query, vector_store, top_k):
    return vector_store.search(query, top_k)
