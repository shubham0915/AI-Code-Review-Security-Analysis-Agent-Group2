"""
app/llm/factory.py — LLM and Embeddings factory.

Returns the correct LLM and embedding model based on LLM_PROVIDER in .env.
Agents import from here — they never hard-code which provider to use.

Usage:
    from app.llm.factory import get_llm, get_fast_llm, get_embeddings

    llm = get_llm()           # primary model (security, remediation)
    fast_llm = get_fast_llm() # fast model (PR summary, quick tasks)
    embeddings = get_embeddings()  # for ChromaDB indexing and search
"""
from __future__ import annotations

from functools import lru_cache
from loguru import logger

from app.config import get_settings


# ─────────────────────────────────────────────────────────────────────────────
# Primary LLM — used by Security Vulnerability Agent + Remediation Agent
# ─────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_llm():
    """Return the primary LLM (heavier, more accurate)."""
    settings = get_settings()

    if settings.using_gemini:
        from langchain_google_genai import ChatGoogleGenerativeAI
        logger.info(f"LLM: Gemini → {settings.gemini_primary_model}")
        return ChatGoogleGenerativeAI(
            model=settings.gemini_primary_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.gemini_temperature,
            convert_system_message_to_human=True,
        )

    # Ollama fallback
    from langchain_community.chat_models import ChatOllama
    logger.info(f"LLM: Ollama → {settings.ollama_primary_model}")
    return ChatOllama(
        model=settings.ollama_primary_model,
        base_url=settings.ollama_base_url,
        temperature=0.1,
        timeout=settings.ollama_timeout,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fast LLM — used by Code Analysis Agent + PR Summary Agent
# ─────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_fast_llm():
    """Return the fast LLM (lower latency, lighter tasks)."""
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


# ─────────────────────────────────────────────────────────────────────────────
# Embeddings — used by ChromaDB indexing + RAG retrieval
# ─────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_embeddings():
    """Return the embedding model for vector store operations."""
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


# ─────────────────────────────────────────────────────────────────────────────
# Provider info — useful for health check and UI display
# ─────────────────────────────────────────────────────────────────────────────
def get_provider_info() -> dict:
    settings = get_settings()
    if settings.using_gemini:
        return {
            "provider": "Gemini API",
            "primary_model": settings.gemini_primary_model,
            "fast_model": settings.gemini_fast_model,
            "embed_model": settings.gemini_embed_model,
            "local": False,
        }
    return {
        "provider": "Ollama (local)",
        "primary_model": settings.ollama_primary_model,
        "fast_model": settings.ollama_fast_model,
        "embed_model": settings.ollama_embed_model,
        "local": True,
    }
