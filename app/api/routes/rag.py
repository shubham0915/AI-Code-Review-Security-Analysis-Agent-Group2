"""
app/api/routes/rag.py — RAG Conversational Assistant endpoint.

POST /api/v1/rag/query
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.rag.indexer import build_or_load_index

router = APIRouter(prefix="/api/v1/rag", tags=["RAG Assistant"])


class QueryRequest(BaseModel):
    question: str
    top_k: int = 3


class SourceNode(BaseModel):
    text: str
    score: float | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceNode]


# We will load the index once globally so it doesn't reload on every request
_query_engine = None


def get_query_engine(top_k: int = 3):
    global _query_engine
    if _query_engine is None:
        logger.info("Initializing RAG query engine...")
        index = build_or_load_index(kb_dir="data/knowledge_base")
        if index is None:
            raise RuntimeError("RAG index could not be loaded. Ensure it is built.")
        _query_engine = index.as_query_engine(similarity_top_k=top_k)
    return _query_engine


@router.post("/query", response_model=QueryResponse)
async def query_assistant(request: QueryRequest) -> QueryResponse:
    try:
        engine = get_query_engine(top_k=request.top_k)
        response = engine.query(request.question)

        sources = []
        for node in response.source_nodes:
            sources.append(
                SourceNode(
                    text=node.node.get_content().replace("\n", " "), score=node.score
                )
            )

        return QueryResponse(answer=str(response).strip(), sources=sources)
    except Exception as e:
        logger.exception("Failed to query RAG assistant")
        raise HTTPException(status_code=500, detail=str(e))
