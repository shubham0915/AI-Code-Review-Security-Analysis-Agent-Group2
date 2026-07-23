"""
app/llm.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PURPOSE: The single source of truth for which AI model to use.
         All agents import their LLM from here — NEVER hard-code
         a model name directly inside an agent file.

         This makes switching between Gemini (cloud) and Ollama (local)
         a one-line change in the .env file.

LLM ROLES:
  get_llm()       → Heavy model (Gemini Pro / Codestral)
                    Used by: Security Agent, Remediation Agent
                    Why: Security needs deep reasoning and code understanding

  get_fast_llm()  → Lighter/faster model (Gemini Flash / Qwen2.5-Coder)
                    Used by: Code Analysis Agent, PR Summary Agent
                    Why: These tasks are simpler and benefit from speed

  get_embeddings() → Embedding model (text-embedding-004 / nomic-embed-text)
                    Used by: RAG indexer and ChromaDB vector search
                    Why: Converts text to mathematical vectors for similarity search

All functions are cached with @lru_cache so the model is only loaded once.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

from functools import lru_cache
from loguru import logger

from app.config import get_settings


@lru_cache(maxsize=1)
def get_llm():
    """
    Return the primary (heavy) LLM for deep reasoning tasks.
    Cached so the model object is only created once per process.

    Provider selection is driven by LLM_PROVIDER in .env:
      - "gemini" → ChatGoogleGenerativeAI (requires GEMINI_API_KEY)
      - "ollama"  → ChatOllama (requires Ollama running locally)
    """
    settings = get_settings()

    if settings.using_gemini:
        from langchain_google_genai import ChatGoogleGenerativeAI
        logger.info(f"LLM: Gemini → {settings.gemini_primary_model}")
        return ChatGoogleGenerativeAI(
            model=settings.gemini_primary_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.gemini_temperature,
            convert_system_message_to_human=True,  # Required for Gemini compatibility
        )

    # Ollama local fallback
    from langchain_community.chat_models import ChatOllama
    logger.info(f"LLM: Ollama → {settings.ollama_primary_model}")
    return ChatOllama(
        model=settings.ollama_primary_model,
        base_url=settings.ollama_base_url,
        temperature=0.1,        # Low temperature = more deterministic, less creative
        timeout=settings.ollama_timeout,
    )


@lru_cache(maxsize=1)
def get_fast_llm():
    """
    Return the fast (lighter) LLM for speed-sensitive tasks.
    Cached so the model object is only created once per process.

    Used by agents that need a quick turnaround and don't require
    the deepest possible reasoning (code quality review, PR summary).
    """
    settings = get_settings()

    if settings.using_gemini:
        from langchain_google_genai import ChatGoogleGenerativeAI
        logger.info(f"Fast LLM: Gemini → {settings.gemini_fast_model}")
        return ChatGoogleGenerativeAI(
            model=settings.gemini_fast_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.gemini_temperature,
            convert_system_message_to_human=True,
        )

    from langchain_community.chat_models import ChatOllama
    logger.info(f"Fast LLM: Ollama → {settings.ollama_fast_model}")
    return ChatOllama(
        model=settings.ollama_fast_model,
        base_url=settings.ollama_base_url,
        temperature=0.1,
        timeout=settings.ollama_timeout,
    )


@lru_cache(maxsize=1)
def get_embeddings():
    """
    Return the embedding model used by ChromaDB.
    An embedding model converts text into a list of numbers (a vector)
    that represents the semantic meaning of that text.

    These vectors are what make ChromaDB's "find similar documents"
    search work — it finds documents whose vectors are mathematically
    close to the query vector.
    """
    settings = get_settings()

    if settings.using_gemini:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        logger.info(f"Embeddings: Gemini → {settings.gemini_embed_model}")
        return GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embed_model,
            google_api_key=settings.gemini_api_key,
        )

    from langchain_community.embeddings import OllamaEmbeddings
    logger.info(f"Embeddings: Ollama → {settings.ollama_embed_model}")
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


def get_provider_info() -> dict:
    """
    Returns metadata about the currently configured LLM provider.
    Used by the GET /health/ready endpoint to display which models are active.
    """
    settings = get_settings()
    if settings.using_gemini:
        return {
            "provider": "Gemini API",
            "primary_model": settings.gemini_primary_model,
            "fast_model": settings.gemini_fast_model,
            "embed_model": settings.gemini_embed_model,
            "local": False,     # Requires internet connection
        }
    return {
        "provider": "Ollama (local)",
        "primary_model": settings.ollama_primary_model,
        "fast_model": settings.ollama_fast_model,
        "embed_model": settings.ollama_embed_model,
        "local": True,          # Runs entirely offline
    }
