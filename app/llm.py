"""
About this file: llm.py
Structure: Conditional instantiation logic for Gemini API or local Ollama models based on environment configuration.
Methods used: get_llm, get_fast_llm, get_provider_info.
"""

from __future__ import annotations

from functools import lru_cache
from loguru import logger

from app.config import get_settings


def get_llm():
    """
    Return the primary (heavy) LLM for deep reasoning tasks.
    
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


def get_fast_llm():
    """
    Return the fast (lighter) LLM for speed-sensitive tasks.

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
