"""A small, local, dependency-light retriever — TF-IDF + cosine similarity
via scikit-learn, not a managed vector search service.

Why TF-IDF instead of embeddings: this project's own corpus-sizing
analysis (CONSTRUCT_COVERAGE.md, "RAG remains correctly deferred") had
already concluded a local vector store is sufficient at this corpus
scale (a few hundred operator docs, a few dozen schema pages, ~66
worked examples) — no managed search service needed. Going one step
further: the retrieval task itself (operator name -> doc page, event
type -> schema page) is fundamentally lexical/keyword matching on a
small, technical-vocabulary corpus, not open-domain semantic search,
and TF-IDF is a well-suited, zero-API-cost, fully-deterministic match
for that — it also avoids adding a new embedding-model dependency (no
Azure embedding deployment is currently provisioned; LLM_PROVIDER's
own gpt-4.1-mini deployment is a chat model, not an embedding one) or a
new vector-index binary dependency (faiss/chroma) this corpus size
doesn't need.

Each of the three routed corpora (construct syntax, ASIM schema,
worked examples) gets its own independent index — built once offline
by build_rag_indexes.py, loaded read-only at query time.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict


class TfidfRetriever:
    def __init__(self, chunks: List[Chunk], vectorizer: TfidfVectorizer, matrix):
        self.chunks = chunks
        self.vectorizer = vectorizer
        self.matrix = matrix

    @classmethod
    def build(cls, chunks: List[Chunk]) -> "TfidfRetriever":
        vectorizer = TfidfVectorizer(
            lowercase=True, stop_words="english", ngram_range=(1, 2), max_features=20000,
        )
        matrix = vectorizer.fit_transform([c.text for c in chunks])
        return cls(chunks, vectorizer, matrix)

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"chunks": self.chunks, "vectorizer": self.vectorizer, "matrix": self.matrix}, f)

    @classmethod
    def load(cls, path: str) -> "TfidfRetriever":
        with open(path, "rb") as f:
            data = pickle.load(f)
        return cls(data["chunks"], data["vectorizer"], data["matrix"])

    def query(self, text: str, k: int = 3) -> List[Chunk]:
        if not text.strip():
            return []
        qvec = self.vectorizer.transform([text])
        sims = cosine_similarity(qvec, self.matrix)[0]
        # argsort ascending, take the last k, reverse for descending score —
        # cheap enough at this corpus size (hundreds to low thousands of
        # chunks) that an exact top-k via full sort needs no special-casing.
        top_idx = sims.argsort()[::-1][:k]
        return [self.chunks[i] for i in top_idx if sims[i] > 0]
