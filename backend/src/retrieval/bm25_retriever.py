import re
from rank_bm25 import BM25Okapi

STOP = {'the', 'a', 'an', 'in', 'on', 'of', 'to', 'for', 'and', 'or', 'how', 'can', 'i', 'is', 'are', 'do', 'what', 'my', 'with', 'sikkim'}


def tokenize(text):
    return [word for word in re.findall(r'\w+', text.lower()) if word not in STOP]


def retrieve(query, chunks, top_k):
    if not chunks:
        return []
    corpus = [tokenize(chunk['retrieval_text_en']) or ['_empty_'] for chunk in chunks]
    scores = BM25Okapi(corpus).get_scores(tokenize(query))
    terms = set(tokenize(query))
    # BM25 can have zero/negative IDF in tiny corpora; lexical overlap still matters.
    hits = [(chunk['_id'], float(score)) for chunk, words, score in zip(chunks, corpus, scores)
            if terms.intersection(words)]
    return sorted(hits, key=lambda pair: pair[1], reverse=True)[:top_k]
