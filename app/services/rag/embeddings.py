"""
About this file: embeddings.py
Structure: Model connection wrapper implementing proactive probing, backoff retries, and offline HuggingFace embedding fallback.
Methods used: get_embedding_model, _test_embedding.
"""

import time
from loguru import logger
from app.config import get_settings

# Module-level singletons — set once on first use
_active_model = None
_model_type: str | None = None  # "gemini" | "ollama" | "fallback"

_RATE_LIMIT_SIGNALS = ("429", "rate", "quota", "resource_exhausted", "too many")


# ─── Private: model initialisation ────────────────────────────────────────────

def _probe_gemini(settings):
    """
    Attempt one embed call to verify Gemini is reachable.
    Returns the model object on success, None on any failure.
    (Pattern adopted from MARATHON's embeddings.py)
    """
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        model = GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embed_model,
            google_api_key=settings.gemini_api_key,
        )
        model.embed_query("probe")  # fast connectivity check
        logger.info(f"[EMBEDDINGS] Gemini probe OK → {settings.gemini_embed_model}")
        return model
    except Exception as e:
        logger.warning(f"[EMBEDDINGS] Gemini probe failed: {e}. Will try Ollama or fallback.")
        return None


def _probe_ollama(settings):
    """Attempt one embed call to verify Ollama is reachable."""
    try:
        from langchain_community.embeddings import OllamaEmbeddings
        model = OllamaEmbeddings(
            model=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
        )
        model.embed_query("probe")
        logger.info(f"[EMBEDDINGS] Ollama probe OK → {settings.ollama_embed_model}")
        return model
    except Exception as e:
        logger.warning(f"[EMBEDDINGS] Ollama probe failed: {e}. Will use local fallback.")
        return None


def _load_local_fallback():
    """
    Load a local sentence-transformers model as the last-resort fallback.
    Works offline — no API key required. (Same pattern as MARATHON)
    """
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("[EMBEDDINGS] Local fallback loaded (all-MiniLM-L6-v2).")
        return model, "fallback"
    except Exception as e:
        logger.error(f"[EMBEDDINGS] Local fallback failed: {e}")
        return None, "none"


def _init():
    """
    Initialise the embedding model exactly once per process.
    Called lazily on first use — safe for async contexts.
    Priority: Gemini → Ollama → local sentence-transformers
    """
    global _active_model, _model_type
    if _active_model is not None:
        return  # Already initialised

    settings = get_settings()

    if settings.using_gemini:
        model = _probe_gemini(settings)
        if model:
            _active_model, _model_type = model, "gemini"
            return

    # Try Ollama (covers local-only mode and Gemini failure)
    model = _probe_ollama(settings)
    if model:
        _active_model, _model_type = model, "ollama"
        return

    # Last resort: fully local
    _active_model, _model_type = _load_local_fallback()


# ─── Private: batch embedding with exponential backoff ────────────────────────

def _embed_batch(batch: list[str]) -> list[list[float]]:
    """
    Embed a batch with up to 4 retry attempts on rate-limit errors.
    Backoff schedule: 1s → 2s → 4s → 8s.
    (Adopted from MARATHON's _embed_batch pattern)
    """
    for attempt in range(4):
        try:
            if _model_type in ("gemini", "ollama"):
                return _active_model.embed_documents(batch)
            else:
                # sentence-transformers API differs
                return _active_model.encode(batch, show_progress_bar=False).tolist()
        except Exception as e:
            err = str(e).lower()
            is_rate_limit = any(sig in err for sig in _RATE_LIMIT_SIGNALS)
            if is_rate_limit and attempt < 3:
                wait = 2 ** attempt  # 1, 2, 4, 8
                logger.warning(
                    f"[EMBEDDINGS] Rate limit hit — retrying in {wait}s "
                    f"(attempt {attempt + 1}/4)."
                )
                time.sleep(wait)
            else:
                logger.error(f"[EMBEDDINGS] embed_batch failed: {e}")
                raise
    raise RuntimeError("[EMBEDDINGS] Rate limit persisted after 4 attempts.")


# ─── Public API ────────────────────────────────────────────────────────────────

BATCH_SIZE = 50


def embed_query(query: str) -> list[float]:
    """Embed a single query string. Safe to call before _init() — initialises lazily."""
    _init()
    if _model_type in ("gemini", "ollama"):
        return _active_model.embed_query(query)
    return _active_model.encode([query])[0].tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts in batches, with rate-limit backoff."""
    _init()
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i: i + BATCH_SIZE]
        logger.debug(f"[EMBEDDINGS] Embedding batch {i}–{i + len(batch)} ({_model_type})")
        all_embeddings.extend(_embed_batch(batch))
    return all_embeddings


def get_active_model():
    """Return the initialised embedding model (for LlamaIndex Settings.embed_model)."""
    _init()
    return _active_model


def get_model_type() -> str:
    """Return the active model type string: 'gemini', 'ollama', or 'fallback'."""
    _init()
    return _model_type or "none"
