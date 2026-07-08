# AI Code Review & Security Analysis Agent

> **Production-grade, multi-agent, RAG-powered platform for automated code security and quality analysis.**
> 100% Open-Source · Zero External API Cost · Runs Locally on Apple M4

[![CI](https://github.com/shubham0915/AI-Code-Review-Security-Analysis-Agent-Group2/actions/workflows/ci.yml/badge.svg)](https://github.com/shubham0915/AI-Code-Review-Security-Analysis-Agent-Group2/actions)

---

## 🚀 Features

| Feature | Status |
|---|---|
| Code Submission (paste + file upload) | ✅ Milestone 1 |
| Language auto-detection (Python/Java) | ✅ Milestone 1 |
| Syntax validation | ✅ Milestone 1 |
| Secure Coding Knowledge Base (OWASP) | 🔄 Milestone 2 |
| Code Analysis Agent | 🔄 Milestone 3 |
| Security Vulnerability Agent (OWASP Top-10) | 🔄 Milestone 3 |
| Remediation Agent | 🔄 Milestone 3 |
| PR Summary Agent | 🔄 Milestone 3 |
| Conversational Code Assistant (RAG) | 🔄 Milestone 4 |
| Report Export (MD/JSON/PDF) | 🔄 Milestone 4 |
| Monitoring (Prometheus + Grafana) | 🔄 Milestone 5 |

---

## 🏗️ Architecture

```
Developer Portal (Streamlit)
       │
FastAPI Backend (/submit /status /result /chat /report)
       │
Celery + Redis (Async task queue)
       │
LangGraph Multi-Agent Pipeline
  ├── Code Analysis Agent     (Pylint + Bandit + LLM)
  ├── Security Vuln Agent     (Semgrep + Bandit + LLM + RAG)
  ├── Remediation Agent       (LLM + RAG)
  └── PR Summary Agent        (LLM)
       │
Ollama (codestral / qwen2.5-coder) ← Local LLMs
ChromaDB (OWASP Knowledge Base) ← Local Vector Store
```

---

## ⚡ Quick Start

### Prerequisites

```bash
# Install Homebrew packages
brew install ollama docker python@3.11 java

# Start Docker Desktop (for Redis/Grafana/Prometheus)
open /Applications/Docker.app
```

### 1. Clone & Setup

```bash
git clone https://github.com/shubham0915/AI-Code-Review-Security-Analysis-Agent-Group2.git
cd AI-Code-Review-Security-Analysis-Agent-Group2

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
```

### 2. Pull Ollama Models

```bash
# Start Ollama (keeps running in background)
ollama serve &

# Pull all required models (~10-15 GB total)
python scripts/setup_ollama.py
```

### 3. Start Infrastructure

```bash
# Start Redis, Prometheus, Grafana
docker-compose up -d

# Verify
docker-compose ps
```

### 4. Start Backend

```bash
# Terminal 1: FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Celery worker
celery -A app.celery_app worker --concurrency=2 -l info
```

### 5. Start Frontend

```bash
# Terminal 3: Streamlit UI
streamlit run frontend/app.py
```

### Access Points

| Service | URL |
|---|---|
| Developer Portal | http://localhost:8501 |
| API Documentation | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin/admin) |

---

## 🧪 Running Tests

```bash
# All tests with coverage
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v
```

---

## 📁 Project Structure

```
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings (pydantic-settings)
│   ├── celery_app.py            # Celery factory
│   ├── api/routes/              # API endpoints
│   │   ├── submit.py            # Code Submission Module ← Milestone 1
│   │   ├── status.py            # Task status polling
│   │   ├── result.py            # Result retrieval
│   │   └── health.py            # Health checks
│   ├── agents/                  # Multi-agent pipeline ← Milestone 3
│   ├── rag/                     # RAG pipeline ← Milestone 2
│   ├── linters/                 # Static analysis wrappers ← Milestone 3
│   ├── models/                  # Pydantic data models
│   ├── cache/                   # Redis cache client
│   ├── tasks/                   # Celery tasks
│   └── utils/                   # Language detection, validation
├── frontend/
│   └── app.py                   # Streamlit Developer Portal
├── scripts/
│   └── setup_ollama.py          # Ollama model setup
├── tests/
│   ├── unit/                    # Unit tests
│   └── integration/             # Integration tests
├── monitoring/
│   └── prometheus.yml           # Prometheus config
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 🔒 Security & Privacy

- **100% Local** — No code leaves your machine
- **No external API calls** — All LLM inference via Ollama
- **OWASP-based analysis** — Covers all OWASP Top-10 categories
- **JWT authentication** — (Milestone 6)

---

## 📅 Milestones

| Milestone | Scope | Status |
|---|---|---|
| M1 (Week 1-2) | Project skeleton + Code Submission Module | ✅ Complete |
| M2 (Week 3-4) | OWASP Knowledge Base + RAG Pipeline | 🔄 Next |
| M3 (Week 5-6) | Multi-Agent Pipeline (4 agents) | 📋 Planned |
| M4 (Week 7-8) | Conversational Assistant + Full UI | 📋 Planned |
| M5 (Week 9-10) | Performance, Monitoring, Testing | 📋 Planned |
| M6 (Week 11-12) | Security hardening + CI/CD | 📋 Planned |

---

## 🤝 Team

Group 2 — AI Code Review & Security Analysis Agent

---

*Built with: FastAPI · LangGraph · LlamaIndex · ChromaDB · Ollama · Streamlit · Celery · Redis*
