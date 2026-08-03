"""
About this file: retriever.py
Structure: Vector similarity query wrappers formatting top-K matching OWASP reference snippets for agent prompts.
Methods used: retrieve_rag_context.
"""

from loguru import logger
from app.services.rag.index import build_or_load_index


# Module-level index cache — loaded once per Celery worker process
_index = None
_index_attempted = False   # Tracks if we've tried loading (avoids repeated failures)


def _get_index():
    """
    Return the cached VectorStoreIndex, loading it lazily on first call.
    Returns None if the knowledge base is not available.
    """
    global _index, _index_attempted
    if _index_attempted:
        return _index  # Return cached result (even if None)
    _index_attempted = True
    try:
        _index = build_or_load_index()
        if _index:
            logger.info("[RETRIEVER] RAG index loaded and cached for this worker.")
        else:
            logger.warning("[RETRIEVER] RAG index not available — agents will run without context.")
    except Exception as e:
        logger.error(f"[RETRIEVER] Failed to load RAG index: {e}")
        _index = None
    return _index


def query_index(query: str, top_k: int = 4) -> str:
    """
    Query the RAG knowledge base and return a formatted context string.

    Args:
        query: Natural language search query.
        top_k: Number of most-similar chunks to retrieve.

    Returns:
        A string with all retrieved chunks concatenated, ready to inject
        into an LLM prompt. Returns an empty string if RAG is unavailable.
    """
    index = _get_index()
    if index is None:
        logger.debug("[RETRIEVER] No index available — returning empty context.")
        return ""

    try:
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)
        context = "\n\n".join(n.text for n in nodes)
        logger.info(f"[RETRIEVER] Query='{query[:60]}' → {len(nodes)} chunks retrieved.")
        return context
    except Exception as e:
        logger.warning(f"[RETRIEVER] Query failed: {e}")
        return ""
