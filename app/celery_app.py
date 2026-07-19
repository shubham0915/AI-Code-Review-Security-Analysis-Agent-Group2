"""
app/celery_app.py — Celery application factory.

Worker: celery -A app.celery_app worker --concurrency=2 -l info
"""

from celery import Celery
from app.config import get_settings

settings = get_settings()

import logfire
from openinference.instrumentation.langchain import LangChainInstrumentor

logfire.configure()
logfire.instrument_celery()
LangChainInstrumentor().instrument()

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
