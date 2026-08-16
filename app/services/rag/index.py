"""
About this file: index.py
Structure: Storage context initialization and document loading workflows handling disk caching and re-indexing.
Methods used: load_or_create_index.
"""
# pylint: disable=import-outside-toplevel, broad-exception-caught
import os
from pathlib import Path
from loguru import logger

import chromadb
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    Settings,
)
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.config import get_settings


def _get_llama_embed_model():
    """
    Return the LlamaIndex-compatible embedding model.
    Uses the probe-backed model from services/rag/embeddings via a LangchainEmbedding wrapper.
    """
    settings = get_settings()
    try:
        from llama_index.embeddings.langchain import LangchainEmbedding
        from app.llm import get_embeddings
        logger.info("[INDEX] Using LangchainEmbedding wrapper for LlamaIndex.")
        return LangchainEmbedding(get_embeddings())
    except Exception as e:
        logger.warning(f"[INDEX] LangchainEmbedding failed: {e}. Falling back to OllamaEmbedding.")
        from llama_index.embeddings.ollama import OllamaEmbedding
        return OllamaEmbedding(
            model_name=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
        )


def _get_llama_llm():
    """Return the LlamaIndex-compatible LLM."""
    settings = get_settings()
    if settings.using_gemini:
        try:
            from llama_index.llms.gemini import Gemini
            logger.info(f"[INDEX] Using LlamaIndex Gemini LLM → {settings.gemini_primary_model}")
            return Gemini(model=settings.gemini_primary_model, api_key=settings.gemini_api_key)
        except Exception as e:
            logger.warning(f"[INDEX] Gemini LLM failed: {e}. Falling back to Ollama.")

    from llama_index.llms.ollama import Ollama
    logger.info(f"[INDEX] Using LlamaIndex Ollama LLM → {settings.ollama_primary_model}")
    return Ollama(
        model=settings.ollama_primary_model,
        base_url=settings.ollama_base_url,
        request_timeout=settings.ollama_timeout,
    )


def build_or_load_index(kb_dir: str = "data/knowledge_base") -> VectorStoreIndex | None:
    """
    Build or load a ChromaDB vector index from the local knowledge base.

    - If the ChromaDB collection already has documents → loads the existing index.
    - If the knowledge base directory is empty or missing → returns None (graceful).
    - If documents exist but no index → builds and persists a new index.

    This is the single entry point for the RAG knowledge base.
    Agents should NOT import chromadb directly — use this function.

    Args:
        kb_dir: Path to the markdown knowledge base directory.

    Returns:
        A LlamaIndex VectorStoreIndex, or None if RAG is not available.
    """
    settings_obj = get_settings()
    db_path = os.path.abspath(settings_obj.chroma_persist_dir)
    os.makedirs(db_path, exist_ok=True)

    Settings.embed_model = _get_llama_embed_model()
    Settings.llm = _get_llama_llm()
    Settings.node_parser = MarkdownNodeParser()

    logger.info(f"[INDEX] Connecting to ChromaDB at: {db_path}")
    db = chromadb.PersistentClient(path=db_path)
    chroma_collection = db.get_or_create_collection(settings_obj.chroma_owasp_collection)

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    doc_count = chroma_collection.count()
    if doc_count > 0:
        logger.info(f"[INDEX] Loaded existing index with {doc_count} chunks.")
        return VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)

    kb_path = Path(kb_dir)
    if not kb_path.exists() or not any(kb_path.iterdir()):
        logger.warning(f"[INDEX] Knowledge base '{kb_dir}' is empty — RAG unavailable.")
        return None

    logger.info(f"[INDEX] Building index from {kb_path.resolve()} …")
    documents = SimpleDirectoryReader(input_dir=str(kb_path)).load_data()
    logger.info(f"[INDEX] Loaded {len(documents)} documents. Embedding …")
    index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context, show_progress=True
    )
    logger.info("[INDEX] Index built and persisted to ChromaDB.")
    return index
