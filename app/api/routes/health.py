"""
app/api/routes/health.py — Health check endpoints.

GET /health
GET /health/ready
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Basic liveness check")
async def health():
    return {"status": "ok", "service": "AI Code Review & Security Analysis Agent"}


@router.get("/health/ready", summary="Readiness check (Redis + Ollama)")
async def ready():
    from app.cache.redis_cache import get_redis_client
    import httpx
    from app.config import get_settings

    settings = get_settings()
    checks = {}

    # Redis
    try:
        redis = await get_redis_client()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            checks["ollama"] = "ok" if resp.status_code == 200 else f"http {resp.status_code}"
    except Exception as e:
        checks["ollama"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"ready": all_ok, "checks": checks},
    )
