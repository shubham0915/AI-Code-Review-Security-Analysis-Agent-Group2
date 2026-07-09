"""
app/api/routes/submit.py — Code Submission Module (Module 1)

Handles:
  POST /api/v1/submit/paste    — Direct code paste
  POST /api/v1/submit/file     — File upload (.py / .java)
  GET  /api/v1/submit/validate — Syntax-only check (no analysis)
"""
from __future__ import annotations

import ast
import hashlib
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import get_settings
from app.models.session import (
    CodeSubmissionRequest,
    Language,
    SubmissionResponse,
    TaskStatus,
    ValidationError,
    SubmissionValidationResponse,
)
from app.utils.language_detector import detect_language
from app.utils.code_validator import validate_code
from app.cache.redis_cache import get_redis_client

router = APIRouter(prefix="/api/v1/submit", tags=["Code Submission"])
settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a cache key for deduplication
# ─────────────────────────────────────────────────────────────────────────────
def _cache_key(code: str, language: str) -> str:
    return "analysis:" + hashlib.sha256(f"{language}:{code}".encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: create and store a session record in Redis
# ─────────────────────────────────────────────────────────────────────────────
async def _create_session(
    code: str,
    language: Language,
    filename: str | None,
) -> SubmissionResponse:
    import json
    from datetime import datetime

    session_id = str(uuid.uuid4())
    loc = len(code.splitlines())

    response = SubmissionResponse(
        session_id=session_id,
        status=TaskStatus.queued,
        language=language,
        filename=filename,
        lines_of_code=loc,
        estimated_seconds=max(30, min(loc // 10, 120)),
    )

    redis = await get_redis_client()
    session_data = {
        "session_id": session_id,
        "status": TaskStatus.queued.value,
        "code": code,
        "language": language.value,
        "filename": filename or "",
        "submitted_at": datetime.utcnow().isoformat(),
    }
    await redis.setex(
        f"session:{session_id}",
        settings.redis_session_ttl,
        json.dumps(session_data),
    )
    logger.info(f"Session created: {session_id} | lang={language.value} | loc={loc}")
    return response


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/submit/paste — Direct code paste
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/paste",
    response_model=SubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit code via direct paste",
    description="Accepts raw source code as JSON. Returns a session ID for polling status.",
)
async def submit_paste(request: CodeSubmissionRequest) -> SubmissionResponse:
    # ── 1. Detect language if auto ──────────────────
    language = request.language
    if language == Language.auto:
        language = detect_language(request.code, request.filename)

    # ── 2. Validate code lines limit ────────────────
    lines = request.code.splitlines()
    if len(lines) > settings.max_code_lines:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Code exceeds maximum {settings.max_code_lines} lines. Got {len(lines)}.",
        )

    # ── 3. Syntax check ─────────────────────────────
    validation = validate_code(request.code, language)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Syntax validation failed.",
                "errors": [e.model_dump() for e in validation.errors],
            },
        )

    # ── 4. Check Redis cache (duplicate submission) ──
    cache_key = _cache_key(request.code, language.value)
    redis = await get_redis_client()
    cached_session = await redis.get(f"cache:{cache_key}")
    if cached_session:
        import json
        cached = json.loads(cached_session)
        logger.info(f"Cache hit for existing analysis: {cached['session_id']}")
        loc = len(request.code.splitlines())
        return SubmissionResponse(
            session_id=cached["session_id"],
            status=TaskStatus.completed,
            language=language,
            lines_of_code=loc,
            estimated_seconds=0,
            message="Returning cached analysis result.",
        )

    # ── 5. Create session + queue Celery task ────────
    submission = await _create_session(request.code, language, request.filename)

    # Queue the full agent pipeline
    from app.tasks.analysis import run_full_analysis
    run_full_analysis.delay(submission.session_id)
    logger.info(f"Queued analysis task for session: {submission.session_id}")

    return submission


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/submit/file — File upload (.py / .java)
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/file",
    response_model=SubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit code via file upload",
    description="Upload a .py or .java file for analysis. Max 5 MB.",
)
async def submit_file(
    file: Annotated[UploadFile, File(description="Python or Java source file")],
    language: Annotated[Language, Form()] = Language.auto,
) -> SubmissionResponse:
    # ── 1. Validate extension ────────────────────────
    filename = file.filename or "uploaded_file"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in settings.allowed_ext_list:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Allowed: {settings.allowed_extensions}",
        )

    # ── 2. Validate file size ────────────────────────
    content = await file.read()
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {len(content) / 1024:.1f} KB exceeds limit of {settings.max_file_size_mb} MB.",
        )

    # ── 3. Decode ────────────────────────────────────
    try:
        code = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File is not valid UTF-8 text.",
        )

    # ── 4. Detect language ───────────────────────────
    if language == Language.auto:
        language = detect_language(code, filename)

    # ── 5. Lines limit ───────────────────────────────
    lines = code.splitlines()
    if len(lines) > settings.max_code_lines:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File has {len(lines)} lines; limit is {settings.max_code_lines}.",
        )

    # ── 6. Syntax check ─────────────────────────────
    validation = validate_code(code, language)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Syntax validation failed.",
                "errors": [e.model_dump() for e in validation.errors],
                "filename": filename,
            },
        )

    # ── 7. Create session + queue ────────────────────
    submission = await _create_session(code, language, filename)
    from app.tasks.analysis import run_full_analysis
    run_full_analysis.delay(submission.session_id)
    logger.info(f"File '{filename}' queued: {submission.session_id}")
    return submission


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/submit/validate — Syntax-only check (no analysis queued)
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/validate",
    response_model=SubmissionValidationResponse,
    summary="Validate code syntax only",
    description="Check if code is syntactically valid. No analysis task is queued.",
)
async def validate_only(request: CodeSubmissionRequest) -> SubmissionValidationResponse:
    language = request.language
    if language == Language.auto:
        language = detect_language(request.code, request.filename)

    result = validate_code(request.code, language)
    return result
