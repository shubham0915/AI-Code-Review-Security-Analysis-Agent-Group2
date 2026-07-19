"""
app/api/routes/health.py — Health check endpoints.

GET /health          → liveness (always returns ok)
GET /health/ready    → readiness (checks Redis + LLM provider)
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Basic liveness check")
async def health():
    return {"status": "ok", "service": "AI Code Review & Security Analysis Agent"}


@router.get("/health/ready", summary="Readiness check (Redis + LLM provider)")
async def ready():
    from app.cache.redis_cache import get_redis_client
    from app.config import get_settings
    from app.llm.factory import get_provider_info

    settings = get_settings()
    checks = {}

    # Redis / in-memory fallback
    try:
        redis = await get_redis_client()
        await redis.ping()
        from app.cache.redis_cache import is_using_memory_fallback

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
