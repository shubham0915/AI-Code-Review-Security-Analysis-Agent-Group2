"""
About this file: tasks.py
Structure: Celery task handler mapping queued submissions through validation, linter execution, and graph orchestration.
Methods used: analyze_code_task, update_task_status.
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
from app.tracing import traceable, log_trace_url

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
        r.publish(f"ws:{session_id}", json.dumps({"type": "status", "status": "running"}))

        logger.info(f"Analysis started: {session_id} | lang={language}")
        print(f"[CELERY] Analysis started: {session_id} | lang={language}", flush=True)

        initial_state = {
            "session_id": session_id,
            "code": code,
            "language": language,
            "linter_output": {},
            "code_analysis_result": None,
            "security_analysis_result": None,
            "remediation_result": None,
            "pr_summary_result": None,
        }
        print("[CELERY] Invoking LangGraph pipeline...", flush=True)

        def pydantic_to_dict(model):
            """Safely serialize a Pydantic model to a dict for Redis JSON storage."""
            return model.model_dump() if model else None

        # ── LangSmith: run the full pipeline inside a named traceable span ──────
        @traceable(
            name="FullAnalysisPipeline",
            run_type="chain",
            metadata={
                "session_id": session_id,
                "language": language,
                "code_length": len(code),
                "filename": session.get("filename", "unknown"),
            },
            project_name="codeANALYSIS",
        )
        async def _invoke_pipeline(state: dict) -> dict:
            """Inner async wrapper to stream events and return final state."""
            current_state = state.copy()
            async for output in analysis_graph.astream(state):
                for node_name, node_output in output.items():
                    print(f"[CELERY] Node completed: {node_name}", flush=True)
                    node_output = node_output or {}
                    current_state.update(node_output)
                    
                    payload = None
                    if node_name == "code_analysis":
                        payload = pydantic_to_dict(node_output.get("code_analysis_result"))
                    elif node_name == "security_vuln":
                        payload = pydantic_to_dict(node_output.get("security_analysis_result"))
                    elif node_name == "remediation":
                        payload = pydantic_to_dict(node_output.get("remediation_result"))
                    elif node_name == "pr_summary":
                        payload = pydantic_to_dict(node_output.get("pr_summary_result"))
                        
                    if payload:
                        msg = {
                            "type": "node_complete",
                            "node": node_name,
                            "data": payload
                        }
                        r.publish(f"ws:{session_id}", json.dumps(msg))
                        
            return current_state

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            final_state = loop.run_until_complete(_invoke_pipeline(initial_state))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        print("[CELERY] LangGraph pipeline completed. Extracting results...", flush=True)

        code_res = final_state.get("code_analysis_result")
        sec_res = final_state.get("security_analysis_result")
        rem_res = final_state.get("remediation_result")
        pr_res = final_state.get("pr_summary_result")

        pipeline_result = {
            "session_id": session_id,
            "language": language,
            "filename": session.get("filename"),
            "code_analysis": pydantic_to_dict(code_res),
            "security_analysis": pydantic_to_dict(sec_res),
            "remediation": pydantic_to_dict(rem_res),
            "pr_summary": pydantic_to_dict(pr_res),
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
        r.publish(f"ws:{session_id}", json.dumps({"type": "status", "status": "completed"}))

        logger.info(f"Analysis completed: {session_id}")
        log_trace_url(session_id)  # Logs LangSmith trace URL to console
        return {"status": "completed", "session_id": session_id}

    except Exception as exc:
        logger.exception(f"Analysis failed for session {session_id}: {exc}")
        session = json.loads(r.get(f"session:{session_id}") or "{}")
        session["status"] = "failed"
        session["error_message"] = str(exc)
        r.setex(f"session:{session_id}", settings.redis_session_ttl, json.dumps(session))
        r.publish(f"ws:{session_id}", json.dumps({"type": "status", "status": "failed", "error": str(exc)}))
        raise self.retry(exc=exc, countdown=10)
