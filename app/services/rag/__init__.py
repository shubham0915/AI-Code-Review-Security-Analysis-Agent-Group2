"""
app/services/rag
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Public API for the RAG knowledge base service layer.

Agents import only from here — never from index.py or embeddings.py directly.
  from app.services.rag import query_index
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from app.services.rag.retriever import query_index
from app.services.rag.index import build_or_load_index   # kept for api/routes/rag.py

__all__ = ["query_index", "build_or_load_index"]
