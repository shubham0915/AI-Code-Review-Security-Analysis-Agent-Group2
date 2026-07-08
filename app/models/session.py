"""
app/models/session.py — Pydantic models for code submission sessions.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Language(str, Enum):
    python = "python"
    java = "java"
    auto = "auto"


class TaskStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class CodeSubmissionRequest(BaseModel):
    """Request body for direct code paste submissions."""
    code: str = Field(..., min_length=1, description="Raw source code to analyze")
    language: Language = Field(Language.auto, description="Programming language")
    filename: Optional[str] = Field(None, description="Optional filename hint")

    model_config = {"json_schema_extra": {
        "example": {
            "code": "import sqlite3\ndef get_user(uid):\n    conn = sqlite3.connect('db')\n    return conn.execute(f'SELECT * FROM users WHERE id={uid}').fetchall()",
            "language": "python",
            "filename": "example.py",
        }
    }}


class SubmissionResponse(BaseModel):
    """Response returned immediately after a successful code submission."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.queued
    language: Language = Language.auto
    filename: Optional[str] = None
    lines_of_code: int = 0
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_seconds: int = Field(45, description="Estimated processing time in seconds")
    message: str = "Code submitted successfully. Analysis queued."

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "status": "queued",
            "language": "python",
            "lines_of_code": 4,
            "estimated_seconds": 45,
            "message": "Code submitted successfully. Analysis queued.",
        }
    }}


class TaskStatusResponse(BaseModel):
    """Response for polling the status of an analysis task."""
    session_id: str
    status: TaskStatus
    progress_pct: int = Field(0, ge=0, le=100, description="Completion percentage")
    current_stage: Optional[str] = Field(None, description="Current agent stage")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ValidationError(BaseModel):
    """Model for code validation errors returned to the client."""
    field: str
    message: str


class SubmissionValidationResponse(BaseModel):
    """Response when submission fails validation."""
    valid: bool = False
    errors: list[ValidationError] = []
    detail: str = "Submission validation failed."
