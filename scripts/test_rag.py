#!/usr/bin/env python3
"""
scripts/test_rag.py

Tests the RAG Knowledge Base by asking a security-related question.
It retrieves relevant chunks from ChromaDB and uses Ollama to generate an answer.
"""

import sys
import time
from pathlib import Path

# pyrefly: ignore [missing-import]
from loguru import logger

# Add root directory to path to load settings and indexer
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag.indexer import build_or_load_index


def main():
    logger.info("Loading RAG database...")
    index = build_or_load_index(kb_dir="data/knowledge_base")

    if not index:
        logger.error("Could not load index. Did you build it first?")
        sys.exit(1)

    logger.info("Initializing query engine...")
    # Create a query engine that retrieves the top 3 most relevant chunks
    query_engine = index.as_query_engine(similarity_top_k=3)

    question = "What is the best way to prevent SQL Injection?"
    logger.info(f"\n[?] Asking: '{question}'\n")

    start_time = time.time()
    response = query_engine.query(question)
    duration = time.time() - start_time

    print("\n" + "=" * 50)
    print("🤖 AI RESPONSE:")
    print("=" * 50)
    print(str(response).strip())
    print("=" * 50)
    print(f"(Answered in {duration:.2f} seconds)\n")

    # Print the source documents that the AI used to answer
    print("📚 SOURCE DOCUMENTS RETRIEVED:")
    for i, node in enumerate(response.source_nodes, 1):
        print(f"\nSource {i}:")
        print("-" * 30)
        # Print first 200 characters of the source text
        text = node.node.get_content().replace("\n", " ")
        print(f"{text[:200]}...")


if __name__ == "__main__":
    main()
