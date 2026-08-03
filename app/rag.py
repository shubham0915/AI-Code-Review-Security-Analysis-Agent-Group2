"""
About this file: rag.py
Structure: Wrapper procedures for checking vector indexes and instantiating retrieval pipelines.
Methods used: build_or_load_index, get_rag_context.
"""

from app.services.rag.index import build_or_load_index  # noqa: F401

__all__ = ["build_or_load_index"]
