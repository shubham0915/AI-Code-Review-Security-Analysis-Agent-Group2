#!/usr/bin/env python3
"""
scripts/build_index.py

Triggers the RAG indexing process. Reads documents from data/knowledge_base,
chunks them, embeds them, and saves the vector store locally in ChromaDB.
"""

import sys
import time
from pathlib import Path
from loguru import logger

# Add root directory to path to load settings and indexer
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag.indexer import build_or_load_index

def main():
    logger.info("Initializing RAG database indexing...")
    start_time = time.time()
    
    # Run the indexer
    index = build_or_load_index(kb_dir="data/knowledge_base")
    
    if index is not None:
        duration = time.time() - start_time
        logger.info(f"Indexing completed successfully in {duration:.2f} seconds.")
    else:
        logger.error("Failed to build index. Check the logs above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
