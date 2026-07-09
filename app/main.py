"""
app/main.py — FastAPI application entry point.

Starts the AI Code Review & Security Analysis Agent API server.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from app.config import get_settings
from app.api.routes import health, submit, status, result, rag
from app.cache.redis_cache import close_redis

settings = get_settings()

from prometheus_client import REGISTRY

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus metrics
# ─────────────────────────────────────────────────────────────────────────────
if "http_requests_total" in REGISTRY._names_to_collectors:
    REQUEST_COUNT = REGISTRY._names_to_collectors["http_requests_total"]
else:
    REQUEST_COUNT = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status_code"],
    )

if "http_request_duration_seconds" in REGISTRY._names_to_collectors:
    REQUEST_LATENCY = REGISTRY._names_to_collectors["http_request_duration_seconds"]
else:
    REQUEST_LATENCY = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
    )

if "code_submissions_total" in REGISTRY._names_to_collectors:
    SUBMISSION_COUNT = REGISTRY._names_to_collectors["code_submissions_total"]
else:
    SUBMISSION_COUNT = Counter(
        "code_submissions_total",
        "Total code submissions",
        ["language", "source"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("AI Code Review & Security Analysis Agent — Starting")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Ollama model: {settings.ollama_primary_model}")
    logger.info(f"Redis: {settings.redis_url}")
    logger.info("=" * 60)
    yield
    logger.info("Shutting down — closing connections...")
    await close_redis()


# ─────────────────────────────────────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Code Review & Security Analysis Agent",
    description=(
        "A production-grade, multi-agent, RAG-powered platform that "
        "automatically analyzes Python and Java source code for security "
        "vulnerabilities, code quality issues, and provides actionable "
        "remediation guidance grounded in OWASP standards."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Prometheus metrics endpoint
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(submit.router)
app.include_router(status.router)
app.include_router(result.router)
app.include_router(rag.router)

@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "AI Code Review & Security Analysis Agent API",
        "docs": "/docs",
        "health": "/health/ready"
    }

# ─────────────────────────────────────────────────────────────────────────────
# Global exception handler
# ─────────────────────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs."},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dev run entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower(),
    )
