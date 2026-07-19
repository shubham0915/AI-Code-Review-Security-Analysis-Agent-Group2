"""
app/rag/indexer.py

Chunking and embedding logic for the Secure Coding Knowledge Base.
Uses LlamaIndex, ChromaDB, and local Ollama models (or Gemini API if configured).
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
            from app.llm.factory import get_embeddings

            logger.info(
                "Using LangchainEmbedding wrapper for Gemini embeddings in LlamaIndex"
            )
            return LangchainEmbedding(get_embeddings())
        except Exception as e:
            logger.error(
                f"Failed to load LangchainEmbedding wrapper: {e}. Falling back to default OllamaEmbedding."
            )

    logger.info(
        f"Configuring OllamaEmbedding: model={settings.ollama_embed_model}, base_url={settings.ollama_base_url}"
    )
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
            return Gemini(
                model=settings.gemini_primary_model, api_key=settings.gemini_api_key
            )
        except Exception as e:
            logger.error(
                f"Failed to load LlamaIndex Gemini LLM: {e}. Falling back to Ollama LLM."
            )

    logger.info(
        f"Configuring Ollama LLM: model={settings.ollama_primary_model}, base_url={settings.ollama_base_url}"
    )
    from llama_index.llms.ollama import Ollama

    return Ollama(
        model=settings.ollama_primary_model,
        base_url=settings.ollama_base_url,
        request_timeout=settings.ollama_timeout,
    )


def build_or_load_index(kb_dir: str = "data/knowledge_base") -> VectorStoreIndex | None:
    """
    Build or load a ChromaDB index from local files in kb_dir.
    Configures chunking chunk_size=512 and chunk_overlap=64 tokens.
    """
    settings = get_settings()

    # 1. Resolve and create DB storage directory
    db_path = os.path.abspath(settings.chroma_persist_dir)
    os.makedirs(db_path, exist_ok=True)

    # 2. Configure LlamaIndex global Settings
    Settings.embed_model = get_llama_embeddings()
    Settings.llm = get_llama_llm()
    Settings.node_parser = MarkdownNodeParser()

    # 3. Create persistent ChromaDB client
    logger.info(f"Connecting to ChromaDB at: {db_path}")
    db = chromadb.PersistentClient(path=db_path)
    chroma_collection = db.get_or_create_collection(settings.chroma_owasp_collection)

    # 4. Construct the vector store and storage context
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # 5. Check if we already have documents in the collection
    doc_count = chroma_collection.count()
    if doc_count > 0:
        logger.info(
            f"Collection '{settings.chroma_owasp_collection}' already exists with {doc_count} chunks. Loading index."
        )
        index = VectorStoreIndex.from_vector_store(
            vector_store, storage_context=storage_context
        )
        return index

    # 6. Parse and build if empty
    kb_path = Path(kb_dir)
    if not kb_path.exists() or not any(kb_path.iterdir()):
        logger.warning(
            f"Knowledge base directory '{kb_dir}' is empty or does not exist. Cannot build index."
        )
        return None

    logger.info(f"Loading files from: {kb_path.resolve()}")
    reader = SimpleDirectoryReader(input_dir=str(kb_path))
    documents = reader.load_data()
    logger.info(f"Successfully loaded {len(documents)} documents.")

    logger.info("Embedding and indexing documents into ChromaDB...")
    index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context, show_progress=True
    )
    logger.info("VectorStoreIndex successfully built and persisted.")
    return index
