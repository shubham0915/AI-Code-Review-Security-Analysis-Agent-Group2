"""
app/tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PURPOSE: Contains the Celery task that runs the full AI analysis pipeline.
         This is the entry point for BACKGROUND processing.

WHEN IS THIS CALLED?
  - When a user submits code via the API, the submit route calls:
      run_full_analysis.delay(session_id)
  - '.delay()' sends the task to the Redis queue without blocking
  - A Celery worker process picks it up and executes run_full_analysis()

WHAT DOES IT DO?
  1. Load the code from the Redis session store
  2. Set the session status to "running"
  3. Build the LangGraph initial state
  4. Invoke the full agent pipeline (linters → code analysis → security)
  5. Save the results to Redis
  6. Set the session status to "completed" (or "failed" on error)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations

import json
import asyncio
import hashlib
from datetime import datetime

import redis as sync_redis
from loguru import logger

from app.celery_app import celery_app
from app.config import get_settings
from app.agents.graph import analysis_graph

print("[CELERY WORKER] analysis_graph imported and ready.", flush=True)


@celery_app.task(
    name="app.tasks.run_full_analysis",
    bind=True,
    max_retries=1,
    soft_time_limit=600,
    time_limit=660,
)
def run_full_analysis(self, session_id: str) -> dict:
    """Entry point for the multi-agent analysis pipeline."""
    settings = get_settings()
    r = sync_redis.from_url(settings.redis_url, decode_responses=True)

    try:
        raw = r.get(f"session:{session_id}")
        if not raw:
            logger.error(f"Session not found: {session_id}")
            return {"error": "session_not_found"}

        session = json.loads(raw)
        code = session["code"]
        language = session["language"]

        session["status"] = "running"
        session["started_at"] = datetime.utcnow().isoformat()
        session["current_stage"] = "preprocessing"
        r.setex(f"session:{session_id}", settings.redis_session_ttl, json.dumps(session))

        logger.info(f"Analysis started: {session_id} | lang={language}")
        print(f"[CELERY] Analysis started: {session_id} | lang={language}", flush=True)

        initial_state = {
            "session_id": session_id,
            "code": code,
            "language": language,
            "linter_output": {},
            "code_analysis_result": None,
            "security_analysis_result": None,
        }
        print("[CELERY] Invoking LangGraph pipeline...", flush=True)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            final_state = loop.run_until_complete(analysis_graph.ainvoke(initial_state))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        print("[CELERY] LangGraph pipeline completed. Extracting results...", flush=True)

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

        r.setex(f"result:{session_id}", settings.redis_cache_ttl_analysis, json.dumps(pipeline_result))

        cache_key = "analysis:" + hashlib.sha256(f"{language}:{code}".encode()).hexdigest()
        r.setex(
            f"cache:{cache_key}",
            settings.redis_cache_ttl_analysis,
            json.dumps({
                "session_id": session_id,
                "language": language,
                "filename": session.get("filename"),
                "submitted_at": session.get("submitted_at"),
            }),
        )

        session["status"] = "completed"
        session["completed_at"] = datetime.utcnow().isoformat()
        session["current_stage"] = "done"
        r.setex(f"session:{session_id}", settings.redis_session_ttl, json.dumps(session))

        logger.info(f"Analysis completed: {session_id}")
        return {"status": "completed", "session_id": session_id}

    except Exception as exc:
        logger.exception(f"Analysis failed for session {session_id}: {exc}")
        session = json.loads(r.get(f"session:{session_id}") or "{}")
        session["status"] = "failed"
        session["error_message"] = str(exc)
        r.setex(f"session:{session_id}", settings.redis_session_ttl, json.dumps(session))
        raise self.retry(exc=exc, countdown=10)
