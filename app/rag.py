"""
app/rag.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PURPOSE: Manages the RAG (Retrieval-Augmented Generation) knowledge base.
         RAG is the technique that gives our AI agents access to a curated
         library of security standards (OWASP, CWE, secure coding guides)
         instead of relying purely on what they learned during training.

HOW IT WORKS:
  1. We load OWASP and secure coding markdown documents from data/knowledge_base/
  2. We split them into small chunks using MarkdownNodeParser
     (respects document structure — never cuts in the middle of a heading)
  3. Each chunk is converted to a vector (embedding) using the LLM
  4. Vectors are stored in ChromaDB (a local vector database)

  At query time:
    - The Security Agent converts a question to a vector
    - ChromaDB finds the 3 most similar knowledge base chunks
    - Those chunks are injected into the agent's prompt as context

TO BUILD THE INDEX (run once before starting the server):
  python scripts/build_index.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

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
from llama_index.embeddings.ollama import OllamaEmbedding

from app.config import get_settings


def get_llama_embeddings():
    """Get the appropriate LlamaIndex embedding model based on settings."""
    settings = get_settings()
    if settings.using_gemini:
        try:
            from llama_index.embeddings.langchain import LangchainEmbedding
            from app.llm import get_embeddings

            logger.info("Using LangchainEmbedding wrapper for Gemini embeddings in LlamaIndex")
            return LangchainEmbedding(get_embeddings())
        except Exception as e:
            logger.error(f"Failed to load LangchainEmbedding wrapper: {e}. Falling back to OllamaEmbedding.")

    logger.info(f"Configuring OllamaEmbedding: model={settings.ollama_embed_model}, base_url={settings.ollama_base_url}")
    return OllamaEmbedding(
        model_name=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


def get_llama_llm():
    """Get the appropriate LlamaIndex LLM model based on settings."""
    settings = get_settings()
    if settings.using_gemini:
        try:
            from llama_index.llms.gemini import Gemini
            logger.info("Using LlamaIndex Gemini LLM")
            return Gemini(model=settings.gemini_primary_model, api_key=settings.gemini_api_key)
        except Exception as e:
            logger.error(f"Failed to load LlamaIndex Gemini LLM: {e}. Falling back to Ollama LLM.")

    logger.info(f"Configuring Ollama LLM: model={settings.ollama_primary_model}, base_url={settings.ollama_base_url}")
    from llama_index.llms.ollama import Ollama
    return Ollama(
        model=settings.ollama_primary_model,
        base_url=settings.ollama_base_url,
        request_timeout=settings.ollama_timeout,
    )


def build_or_load_index(kb_dir: str = "data/knowledge_base") -> VectorStoreIndex | None:
    """Build or load a ChromaDB index from local files in kb_dir."""
    settings = get_settings()

    db_path = os.path.abspath(settings.chroma_persist_dir)
    os.makedirs(db_path, exist_ok=True)

    Settings.embed_model = get_llama_embeddings()
    Settings.llm = get_llama_llm()
    Settings.node_parser = MarkdownNodeParser()

    logger.info(f"Connecting to ChromaDB at: {db_path}")
    db = chromadb.PersistentClient(path=db_path)
    chroma_collection = db.get_or_create_collection(settings.chroma_owasp_collection)

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    doc_count = chroma_collection.count()
    if doc_count > 0:
        logger.info(f"Collection '{settings.chroma_owasp_collection}' already exists with {doc_count} chunks. Loading index.")
        return VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)

    kb_path = Path(kb_dir)
    if not kb_path.exists() or not any(kb_path.iterdir()):
        logger.warning(f"Knowledge base directory '{kb_dir}' is empty or does not exist. Cannot build index.")
        return None

    logger.info(f"Loading files from: {kb_path.resolve()}")
    documents = SimpleDirectoryReader(input_dir=str(kb_path)).load_data()
    logger.info(f"Successfully loaded {len(documents)} documents.")

    logger.info("Embedding and indexing documents into ChromaDB...")
    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context, show_progress=True)
    logger.info("VectorStoreIndex successfully built and persisted.")
    return index
