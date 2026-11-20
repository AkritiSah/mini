import re
from math import log1p
from rank_bm25 import BM25Okapi

STOP = {'the', 'a', 'an', 'in', 'on', 'of', 'to', 'for', 'and', 'or', 'how', 'can', 'i', 'is', 'are', 'do', 'what', 'my', 'with', 'sikkim'}


def tokenize(text):
    return [word for word in re.findall(r'\w+', text.lower().replace('_', ' ')) if word not in STOP]


def retrieve(query, chunks, top_k):
    if not chunks:
        return []
    corpus = [tokenize(' '.join(str(chunk.get(key) or '') for key in (
        'retrieval_text_en', 'title', 'filename', 'section', 'crop', 'topic', 'source_organization'
    ))) or ['_empty_'] for chunk in chunks]
    model = BM25Okapi(corpus)
    # Keep frequent terms useful in small libraries: negative IDF otherwise ranks
    # a weak match above a passage containing all of the requested terms.
    frequencies = {}
    for words in corpus:
        for word in set(words):
            frequencies[word] = frequencies.get(word, 0) + 1
    model.idf = {word: log1p((len(corpus) - count + .5) / (count + .5))
                 for word, count in frequencies.items()}
    scores = model.get_scores(tokenize(query))
    terms = set(tokenize(query))
    hits = [(chunk['_id'], float(score)) for chunk, words, score in zip(chunks, corpus, scores)
            if terms.intersection(words)]
    return sorted(hits, key=lambda pair: pair[1], reverse=True)[:top_k]
