"""
app/tasks/analysis.py — Celery task: full multi-agent analysis pipeline.

This is the stub for Milestone 1. The actual agent execution will be
wired in Milestone 3 when all agents are implemented.
"""
from __future__ import annotations

import json
from datetime import datetime

import hashlib
import redis as sync_redis

from loguru import logger
from app.celery_app import celery_app
from app.config import get_settings


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
    settings = get_settings()
    r = sync_redis.from_url(settings.redis_url, decode_responses=True)

    try:
        # Load session
        raw = r.get(f"session:{session_id}")
        if not raw:
            logger.error(f"Session not found: {session_id}")
            return {"error": "session_not_found"}

        session = json.loads(raw)
        code = session["code"]
        language = session["language"]

        # Update status: running
        session["status"] = "running"
        session["started_at"] = datetime.utcnow().isoformat()
        session["current_stage"] = "preprocessing"
        r.setex(f"session:{session_id}", settings.redis_session_ttl, json.dumps(session))

        logger.info(f"Analysis started: {session_id} | lang={language}")
        print(f"[CELERY] Analysis started: {session_id} | lang={language}", flush=True)

        # ---- Patch asyncio for Celery compatibility ----
        # asyncio.run() fails inside Celery workers that already have an event loop.
        # We use nest_asyncio as a fallback.
        import asyncio
        from app.agents.graph import analysis_graph

        # Run the agent pipeline
        initial_state = {
            "session_id": session_id,
            "code": code,
            "language": language,
            "linter_output": {},
            "code_analysis_result": None,
            "security_analysis_result": None
        }
        print(f"[CELERY] Invoking LangGraph pipeline...", flush=True)
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We are inside an already-running event loop (shouldn't happen in
                # a standard Celery worker, but handle it defensively)
                import nest_asyncio
                nest_asyncio.apply()
                final_state = loop.run_until_complete(analysis_graph.ainvoke(initial_state))
            else:
                final_state = asyncio.run(analysis_graph.ainvoke(initial_state))
        except RuntimeError:
            # No running loop at all — create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                final_state = loop.run_until_complete(analysis_graph.ainvoke(initial_state))
            finally:
                loop.close()
        
        print(f"[CELERY] LangGraph pipeline completed. Extracting results...", flush=True)
        
        # Extract results
        code_res = final_state.get("code_analysis_result")
        sec_res = final_state.get("security_analysis_result")
        
        def pydantic_to_dict(model):
            return model.model_dump() if model else None

        pipeline_result = {
            "session_id": session_id,
            "language": language,
            "filename": session.get("filename"),
            "code_analysis": pydantic_to_dict(code_res),
            "security_analysis": pydantic_to_dict(sec_res),
            "remediation": None,
            "pr_summary": None,
            "error": None,
        }

        # Store result
        r.setex(
            f"result:{session_id}",
            settings.redis_cache_ttl_analysis,
            json.dumps(pipeline_result),
        )

        # Store cache key for deduplication
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

        # Update status: completed
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
