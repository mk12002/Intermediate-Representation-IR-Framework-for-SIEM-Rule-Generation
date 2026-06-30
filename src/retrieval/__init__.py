"""Local TF-IDF retrieval for the IR Builder's RAG capability (§4AB).

Public interface:
    TfidfRetriever  — build/save/load/query
    Chunk           — a single indexed document chunk

Setup:
    See src/retrieval/build_indexes.py for index-build instructions and
    corpus clone commands. CLAUDE.md §RAG has the one-page summary.

Usage (runtime, inside IRBuilderAgent):
    retriever = TfidfRetriever.load("data/rag_indexes/construct.pkl")
    chunks = retriever.query("parse extract field from command line", k=2)
    for chunk in chunks:
        print(chunk.metadata["title"], chunk.text[:200])
"""
from src.retrieval.retriever import Chunk, TfidfRetriever

__all__ = ["Chunk", "TfidfRetriever"]
