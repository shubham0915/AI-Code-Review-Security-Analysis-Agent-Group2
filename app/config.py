"""
app/config.py — Centralised settings loader using pydantic-settings.
All values fall back to .env file, then to hardcoded defaults.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = "dev-secret-key-change-in-production"
    log_level: str = "INFO"

    # ── LLM Provider toggle ──────────────────────────────────────
    # "gemini" → uses Gemini API (fast, free tier, needs internet)
    # "ollama" → uses local Ollama (private, offline, needs install)
    llm_provider: str = "gemini"

    # ── Gemini API ───────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_primary_model: str = "gemini-2.0-flash"
    gemini_fast_model: str = "gemini-2.0-flash"
    gemini_embed_model: str = "models/text-embedding-004"
    gemini_temperature: float = 0.1

    # ── Ollama (local, fallback) ─────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_primary_model: str = "codestral"
    ollama_fast_model: str = "qwen2.5-coder:7b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout: int = 120

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma_db"
    chroma_owasp_collection: str = "owasp_knowledge_base"
    chroma_patterns_collection: str = "code_patterns"
    chroma_remediation_collection: str = "remediation_guides"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl_analysis: int = 3600
    redis_cache_ttl_embedding: int = 86400
    redis_cache_ttl_llm: int = 3600
    redis_session_ttl: int = 1800

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_worker_concurrency: int = 2

    # Code Submission Limits
    max_code_lines: int = 10000
    max_file_size_mb: int = 5
    allowed_extensions: str = ".py,.java"

    # JWT
    jwt_secret_key: str = "dev-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # Data Retention
    analysis_retention_days: int = 30
    log_retention_days: int = 7

    @property
    def allowed_ext_list(self) -> list[str]:
        return [e.strip() for e in self.allowed_extensions.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def using_gemini(self) -> bool:
        return self.llm_provider.lower() == "gemini"

    @property
    def using_ollama(self) -> bool:
        return self.llm_provider.lower() == "ollama"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
