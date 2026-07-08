"""
app/api/routes/status.py — Task status polling endpoint.

GET /api/v1/status/{session_id}
"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from app.cache.redis_cache import get_redis_client
from app.models.session import TaskStatus, TaskStatusResponse

router = APIRouter(prefix="/api/v1/status", tags=["Task Status"])


@router.get(
    "/{session_id}",
    response_model=TaskStatusResponse,
    summary="Poll analysis task status",
    description="Returns current status and progress for a submitted code analysis task.",
)
async def get_status(session_id: str) -> TaskStatusResponse:
    redis = await get_redis_client()
    raw = await redis.get(f"session:{session_id}")

    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found or has expired.",
        )

    data = json.loads(raw)
    task_status = TaskStatus(data.get("status", TaskStatus.queued))

    # Map status to progress percentage
    progress_map = {
        TaskStatus.queued: 0,
        TaskStatus.running: 50,
        TaskStatus.completed: 100,
        TaskStatus.failed: 0,
    }

    return TaskStatusResponse(
        session_id=session_id,
        status=task_status,
        progress_pct=progress_map.get(task_status, 0),
        current_stage=data.get("current_stage"),
        started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
        completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        error_message=data.get("error_message"),
    )
