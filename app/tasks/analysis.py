"""
app/tasks/analysis.py — Celery task: full multi-agent analysis pipeline.

This is the stub for Milestone 1. The actual agent execution will be
wired in Milestone 3 when all agents are implemented.
"""
from __future__ import annotations

import json
from datetime import datetime

from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.analysis.run_full_analysis",
    bind=True,
    max_retries=2,
    soft_time_limit=300,   # 5 minutes
)
def run_full_analysis(self, session_id: str) -> dict:
    """
    Entry point for the multi-agent analysis pipeline.

    Stages (to be implemented in Milestone 3):
      1. Preprocess: language detect, AST parse, linters
      2. Parallel: Code Analysis Agent + Security Vulnerability Agent
      3. Sequential: Remediation Agent
      4. Sequential: PR Summary Agent
      5. Store result in Redis, update session status
    """
    import redis as sync_redis
    from app.config import get_settings

    settings = get_settings()
    r = sync_redis.from_url(settings.redis_url, decode_responses=True)

    try:
        # ── Load session ─────────────────────────────
        raw = r.get(f"session:{session_id}")
        if not raw:
            logger.error(f"Session not found: {session_id}")
            return {"error": "session_not_found"}

        session = json.loads(raw)
        code = session["code"]
        language = session["language"]

        # ── Update status: running ───────────────────
        session["status"] = "running"
        session["started_at"] = datetime.utcnow().isoformat()
        session["current_stage"] = "preprocessing"
        r.setex(f"session:{session_id}", settings.redis_session_ttl, json.dumps(session))

        logger.info(f"Analysis started: {session_id} | lang={language}")

        # ────────────────────────────────────────────
        # MILESTONE 3 TODO: wire agent pipeline here
        # ────────────────────────────────────────────
        # from app.agents.graph import run_pipeline
        # result = asyncio.run(run_pipeline(session_id, code, language))
        # ────────────────────────────────────────────

        # Placeholder result for Milestone 1 testing
        placeholder_result = {
            "session_id": session_id,
            "language": language,
            "filename": session.get("filename"),
            "code_analysis": None,
            "security_analysis": None,
            "remediation": None,
            "pr_summary": None,
            "error": "Agent pipeline not yet implemented (Milestone 3).",
        }

        # ── Store result ─────────────────────────────
        r.setex(
            f"result:{session_id}",
            settings.redis_cache_ttl_analysis,
            json.dumps(placeholder_result),
        )

        # ── Store cache key for deduplication ─────────
        import hashlib
        cache_key = "analysis:" + hashlib.sha256(f"{language}:{code}".encode()).hexdigest()
        cache_data = {
            "session_id": session_id,
            "language": language,
            "filename": session.get("filename"),
            "submitted_at": session.get("submitted_at")
        }
        r.setex(
            f"cache:{cache_key}",
            settings.redis_cache_ttl_analysis,
            json.dumps(cache_data),
        )

        # ── Update status: completed ─────────────────
        session["status"] = "completed"
        session["completed_at"] = datetime.utcnow().isoformat()
        session["current_stage"] = "done"
        r.setex(f"session:{session_id}", settings.redis_session_ttl, json.dumps(session))

        logger.info(f"Analysis completed (placeholder): {session_id}")
        return {"status": "completed", "session_id": session_id}

    except Exception as exc:
        logger.exception(f"Analysis failed for session {session_id}: {exc}")
        session = json.loads(r.get(f"session:{session_id}") or "{}")
        session["status"] = "failed"
        session["error_message"] = str(exc)
        r.setex(f"session:{session_id}", settings.redis_session_ttl, json.dumps(session))
        raise self.retry(exc=exc, countdown=10)
