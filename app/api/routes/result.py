"""
app/api/routes/result.py — Retrieve completed analysis results.

GET /api/v1/result/{session_id}
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from app.cache import get_redis_client
from app.models import FullAnalysisResult, TaskStatus

router = APIRouter(prefix="/api/v1/result", tags=["Analysis Results"])


@router.get(
    "/{session_id}",
    response_model=FullAnalysisResult,
    summary="Get full analysis result",
    description="Returns the complete multi-agent analysis result for a completed session.",
)
async def get_result(session_id: str) -> FullAnalysisResult:
    redis = await get_redis_client()

    # Check session exists
    session_raw = await redis.get(f"session:{session_id}")
    if not session_raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found or has expired.",
        )

    session_data = json.loads(session_raw)
    current_status = TaskStatus(session_data.get("status", "queued"))

    if current_status == TaskStatus.queued:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Analysis has not started yet. Please wait.",
        )

    if current_status == TaskStatus.running:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Analysis is still running. Please poll /api/v1/status for progress.",
        )

    if current_status == TaskStatus.failed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {session_data.get('error_message', 'Unknown error')}",
        )

    # Fetch result
    result_raw = await redis.get(f"result:{session_id}")
    if not result_raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis result not found. It may have expired.",
        )

    return FullAnalysisResult.model_validate_json(result_raw)
