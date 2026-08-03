"""
About this file: health.py
Structure: FastAPI route definitions verifying internal responsiveness and external dependencies (Redis, LLMs).
Methods used: health, ready.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Basic liveness check")
async def health():
    """
    Returns a basic JSON response indicating the service is alive.
    Used for basic load-balancer liveness checks.
    """
    return {"status": "ok", "service": "AI Code Review & Security Analysis Agent"}


@router.get("/health/ready", summary="Readiness check (Redis + LLM provider)")
async def ready():
    """
    About this file: health.py
    Structure: API Routes.
    Methods used: health, ready.

    Performs a deep health check of external dependencies (Redis and the LLM provider).
    Returns 200 OK if all external services are reachable, else 503 Service Unavailable.
    """
    from app.cache import get_redis_client, is_using_memory_fallback
    from app.config import get_settings
    from app.llm import get_provider_info

    settings = get_settings()
    checks = {}

    # Redis / in-memory fallback
    try:
        redis = await get_redis_client()
        await redis.ping()
        if is_using_memory_fallback():
            checks["cache"] = "in-memory (Redis not running)"
        else:
            checks["cache"] = "ok (Redis)"
    except Exception as e:
        checks["cache"] = f"error: {e}"

    # LLM provider check
    provider = get_provider_info()
    if settings.using_gemini:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params={"key": settings.gemini_api_key},
                )
                checks["llm"] = (
                    f"ok (Gemini API - {provider['primary_model']})"
                    if resp.status_code == 200
                    else f"Gemini error: HTTP {resp.status_code}"
                )
        except Exception as e:
            checks["llm"] = f"Gemini unreachable: {e}"
    else:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                checks["llm"] = (
                    f"ok (Ollama - {provider['primary_model']})"
                    if resp.status_code == 200
                    else f"Ollama error: HTTP {resp.status_code}"
                )
        except Exception as e:
            checks["llm"] = f"Ollama unreachable: {e}"

    all_ok = not any(
        "error" in v.lower() or "unreachable" in v.lower() for v in checks.values()
    )
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "ready": all_ok,
            "provider": provider,
            "checks": checks,
        },
    )