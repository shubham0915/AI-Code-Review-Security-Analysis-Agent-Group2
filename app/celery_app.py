"""
app/celery_app.py — Celery application factory.

Worker: celery -A app.celery_app worker --concurrency=2 -l info
"""

from celery import Celery
from app.config import get_settings

settings = get_settings()

import logfire

# openinference is an optional observability dependency.
# Guard the import so CI (and any environment without it) doesn't crash.
try:
    from openinference.instrumentation.langchain import LangChainInstrumentor as _LangChainInstrumentor
except ImportError:
    _LangChainInstrumentor = None

logfire.configure()
logfire.instrument_celery()

if _LangChainInstrumentor is not None:
    try:
        _LangChainInstrumentor().instrument()
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("LangChain instrumentation disabled: %s", _e)
else:
    import logging
    logging.getLogger(__name__).info("openinference not installed; skipping LangChain instrumentation")

celery_app = Celery(
    "ai_code_review",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.analysis"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    task_routes={
        "app.tasks.analysis.*": {"queue": "analysis"},
    },
)
