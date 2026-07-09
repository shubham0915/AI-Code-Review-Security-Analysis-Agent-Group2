# 🔄 AI Code Review & Security Analysis Agent — Project Handover Summary

*Please review this summary to understand the project's current state and constraints.*

---

## 📌 Project Overview
We are building a **production-grade AI Code Review & Security Analysis Agent** (Group 2).
- **Core Goal**: A multi-agent system that analyzes Python and Java code for OWASP vulnerabilities, code smells, and provides remediation.
- **Constraints**: 100% free, open-source, and runs entirely locally on an **Apple Silicon (M4)** Mac. No paid APIs.
- **Stack**: FastAPI, Streamlit, Celery, Redis, ChromaDB, LangGraph, Ollama.

## ✅ What Has Been Completed (Milestone 1)

**1. Codebase & Repository Setup**
- Cloned repo: `https://github.com/shubham0915/AI-Code-Review-Security-Analysis-Agent-Group2`
- Initialized virtual environment (`.venv`) and installed all core packages (`fastapi`, `streamlit`, `celery`, `pydantic-settings`, etc.).
- Wrote a highly detailed `README.md` containing 5 Mermaid architecture diagrams, a tech stack breakdown, and an OWASP Top-10 mapping.
- Pushed everything to the `main` branch via SSH.

**2. Core Application Infrastructure**
- **FastAPI backend** (`app/main.py`) configured for `localhost:8000`.
- **Streamlit frontend** (`frontend/app.py`) configured for `localhost:8501`. Features a dark glassmorphism UI, code pasting with Monaco editor, and file uploads.
- **Cache Fallback Logic**: Added graceful fallback to an **in-memory store** (`memory_store.py`) if Redis isn't running, allowing the API and UI to function standalone for demos.

**3. Code Submission Module**
- Implemented `/api/v1/submit/paste` and `/api/v1/submit/file`.
- Python AST validation and Java pre-validation (brace/class checks) are fully working.
- Auto-language detection implemented using Pygments.
- Comprehensive unit tests written (`test_code_validator.py`) and passing (15/15).

**4. LLM Factory & Config**
- Configured `app/llm/factory.py` to route LLM calls. 
- Attempted to use the Gemini API free tier, but hit a region/quota limit (`limit: 0`). 
- **Decision:** We are strictly using **Ollama locally** to ensure the project remains free and unblocked. `.env` is set to `LLM_PROVIDER=ollama`.

## 💻 Local Machine Environment & Dependencies Status

Here is the exact status of the local M4 environment and the order of dependencies:

| # | What | Why it's needed | Status |
|---|---|---|---|
| 1 | **Homebrew** | Needed to install Redis | ✅ Installed |
| 2 | **Redis** | Sessions + Celery queue | ✅ Installed & Running |
| 3 | **Ollama** | Run LLMs locally (AI agents) | ✅ Installed & Running |
| 4 | **Celery worker** | Background analysis pipeline | 🟡 Needs to be started |
| 5 | **Ollama models** | 3 models (`nomic-embed-text`, `qwen2.5-coder:7b`, `codestral`) | ✅ All Downloaded |
| 6 | **Docker** | Prometheus/Grafana monitoring | 🟢 Skip for now (Milestone 5) |


## 🚀 Immediate Next Steps (Start Here)

Now that the infrastructure is up and Ollama models are downloaded, we need to begin **Milestone 2: The Secure Coding Knowledge Base (RAG)**.

Please execute the following tasks:

1. **Build the OWASP Knowledge Base (`scripts/download_kb.py`)**
   - Write a script to scrape/download OWASP Cheat Sheets, ASVS, and CWE Top-25 content.
2. **Chunking & Embeddings (`app/rag/indexer.py`)**
   - Implement the logic to chunk the downloaded documents using LlamaIndex/LangChain.
   - Embed them using the local `nomic-embed-text` model via Ollama.
3. **Vector Store (`scripts/build_index.py`)**
   - Save the embeddings into our local persistent ChromaDB (`data/chroma_db/`).
4. **Start the Celery Worker**
   - Run the Celery worker (`celery -A app.celery_app worker --concurrency=2 -l info`) so submitted code in the UI is picked up by background workers instead of just staying "Queued".
