"""
About this file: tracing.py
Structure: Decorator utilities embedding Logfire spans and LangSmith run tracking across agent execution steps.
Methods used: traceable, check_langsmith_connection.
"""

from __future__ import annotations

import os
from loguru import logger

# ── Re-export @traceable so the rest of the app imports from here ──────────────
try:
    from langsmith import traceable, Client as LangSmithClient  # type: ignore
    _LANGSMITH_AVAILABLE = True
except ImportError:
    _LANGSMITH_AVAILABLE = False
    # Fallback no-op decorator — never crashes the app if langsmith missing
    def traceable(*args, **kwargs):  # type: ignore
        """No-op if langsmith is not installed."""
        def decorator(fn):
            """
    Wraps target functions with tracing spans to record parameters, latency, and outputs to Logfire and LangSmith.
    """
            return fn
        # Handle both @traceable and @traceable(name="...") usage
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator

    LangSmithClient = None  # type: ignore


def check_langsmith_connection() -> bool:
    """
    Verify LangSmith connectivity on startup.
    Logs a clear message so you know tracing is active.
    Never raises — a bad key just means tracing is silently skipped.
    """
    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY", "")
    tracing_on = os.getenv("LANGSMITH_TRACING", os.getenv("LANGCHAIN_TRACING_V2", "false")).lower() == "true"
    project = os.getenv("LANGSMITH_PROJECT", os.getenv("LANGCHAIN_PROJECT", "default"))

    if not tracing_on:
        logger.info("[LangSmith] Tracing DISABLED (LANGSMITH_TRACING != true)")
        return False

    if not api_key or api_key.startswith("<"):
        logger.warning("[LangSmith] Tracing enabled but LANGSMITH_API_KEY is missing/placeholder — traces will NOT be sent.")
        return False

    if not _LANGSMITH_AVAILABLE:
        logger.warning("[LangSmith] langsmith package not installed — install with: pip install langsmith")
        return False

    try:
        client = LangSmithClient(api_key=api_key)
        # Quick connectivity check: list projects (lightweight API call)
        list(client.list_projects(limit=1))
        logger.success(
            f"[LangSmith] ✅ Connected! Tracing active → project='{project}' | "
            f"Dashboard: https://smith.langchain.com"
        )
        return True
    except Exception as exc:
        logger.warning(f"[LangSmith] Could not connect ({exc}). Traces may not appear in dashboard.")
        return False


def log_trace_url(session_id: str) -> None:
    """
    Log the LangSmith trace URL for a given session after analysis completes.
    The URL format is stable — you can open it directly in a browser.
    """
    project = os.getenv("LANGSMITH_PROJECT", os.getenv("LANGCHAIN_PROJECT", "default"))
    logger.info(
        f"[LangSmith] 🔍 View trace for session {session_id}: "
        f"https://smith.langchain.com → project '{project}' → filter by metadata session_id={session_id}"
    )