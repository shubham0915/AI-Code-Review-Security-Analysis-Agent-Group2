"""
frontend/app.py — Streamlit Developer Portal

AI Code Review & Security Analysis Agent — Milestone 1
Features:
  - Code paste with syntax-highlighted editor
  - File upload (.py / .java)
  - Live validation feedback
  - Session tracking + status polling
  - Works with OR without the FastAPI backend (graceful fallback)
"""
from __future__ import annotations

import time
import json
import uuid
import ast
from datetime import datetime
from typing import Optional
# pyrefly: ignore [missing-import]
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Page config — MUST be the very first Streamlit call
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Code Review Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/shubham0915/AI-Code-Review-Security-Analysis-Agent-Group2",
        "Report a bug": "https://github.com/shubham0915/AI-Code-Review-Security-Analysis-Agent-Group2/issues",
        "About": "AI Code Review & Security Analysis Agent — Group 2",
    },
)

API_BASE = "http://localhost:8000"

# ─────────────────────────────────────────────────────────────────────────────
# CSS — Dark glassmorphism premium theme
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0a0a14 0%, #0f1020 40%, #0a1628 100%);
    color: #e2e8f0;
    min-height: 100vh;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.03) !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
}
section[data-testid="stSidebar"] .stMarkdown { color: #94a3b8; }

/* Main content area */
.main .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }

/* Cards */
.glass-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 20px 24px;
    margin: 10px 0;
    backdrop-filter: blur(10px);
}
.glass-card-green  { border-left: 4px solid #10b981; }
.glass-card-red    { border-left: 4px solid #ef4444; }
.glass-card-blue   { border-left: 4px solid #6366f1; }
.glass-card-yellow { border-left: 4px solid #f59e0b; }

/* Header */
.main-header { text-align: center; padding: 10px 0 20px; }
.main-header h1 {
    font-size: 2.6rem; font-weight: 800;
    background: linear-gradient(135deg, #6366f1 0%, #a78bfa 50%, #38bdf8 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 6px; letter-spacing: -0.5px;
}
.main-header .subtitle { color: #64748b; font-size: 1.05rem; font-weight: 400; }
.main-header .badges { margin-top: 12px; }

/* Severity badges */
.badge {
    display: inline-block; border-radius: 6px;
    padding: 3px 10px; font-size: 12px; font-weight: 600;
    margin: 2px 4px 2px 0;
}
.badge-critical { background: rgba(127,29,29,0.6); color: #fca5a5; border: 1px solid #7f1d1d; }
.badge-high     { background: rgba(124,45,18,0.6); color: #fdba74; border: 1px solid #7c2d12; }
.badge-medium   { background: rgba(113,63,18,0.6); color: #fde68a; border: 1px solid #713f12; }
.badge-low      { background: rgba(6,78,59,0.6);  color: #6ee7b7; border: 1px solid #064e3b; }
.badge-info     { background: rgba(30,58,95,0.6); color: #93c5fd; border: 1px solid #1e3a5f; }
.badge-ok       { background: rgba(5,46,22,0.6);  color: #86efac; border: 1px solid #052e16; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    padding: 0.55rem 1.4rem !important; font-size: 0.9rem !important;
    transition: all 0.2s ease !important; letter-spacing: 0.01em !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 24px rgba(99,102,241,0.45) !important;
}
.stButton > button[kind="secondary"] {
    background: rgba(255,255,255,0.07) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
}

/* Text area (code input) */
.stTextArea textarea {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important; line-height: 1.6 !important;
    background: #0d1117 !important; color: #c9d1d9 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 10px !important;
}
.stTextArea textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
}

/* Select boxes */
.stSelectbox > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important; color: #e2e8f0 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.03);
    border-radius: 12px; padding: 4px; gap: 4px;
    border: 1px solid rgba(255,255,255,0.07);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important; color: #64748b !important;
    font-weight: 500 !important; padding: 8px 20px !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(99,102,241,0.18) !important;
    color: #a5b4fc !important;
}

/* Metric */
[data-testid="stMetricValue"] { color: #a5b4fc !important; font-size: 1.6rem !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; }
[data-testid="stMetricDelta"] { font-size: 0.85rem !important; }

/* Dividers */
hr { border-color: rgba(255,255,255,0.06) !important; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.03) !important;
    border: 2px dashed rgba(99,102,241,0.4) !important;
    border-radius: 12px !important; padding: 16px !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 8px !important; color: #94a3b8 !important;
}

/* Alert boxes */
.stAlert { border-radius: 10px !important; }

/* Code blocks */
code { background: rgba(99,102,241,0.12) !important; color: #c4b5fd !important; border-radius: 4px !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────────────────────────────────────
if "sessions" not in st.session_state:
    st.session_state.sessions = []
if "api_mode" not in st.session_state:
    st.session_state.api_mode = "checking"


# ─────────────────────────────────────────────────────────────────────────────
# API + standalone helpers
# ─────────────────────────────────────────────────────────────────────────────
def check_api() -> bool:
    try:
        # pyrefly: ignore [missing-import]
        import httpx
        r = httpx.get(f"{API_BASE}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def api_validate(code: str, language: str) -> dict:
    try:
        # pyrefly: ignore [missing-import]
        import httpx
        r = httpx.post(f"{API_BASE}/api/v1/submit/validate",
                       json={"code": code, "language": language}, timeout=10)
        return r.json()
    except Exception:
        return _local_validate(code, language)


def api_submit_paste(code: str, language: str, filename: str = "") -> dict:
    try:
        # pyrefly: ignore [missing-import]
        import httpx
        payload = {"code": code, "language": language}
        if filename:
            payload["filename"] = filename
        r = httpx.post(f"{API_BASE}/api/v1/submit/paste", json=payload, timeout=15)
        return r.json()
    except Exception:
        return _local_submit(code, language, filename)


def api_submit_file(file_bytes: bytes, filename: str, language: str) -> dict:
    try:
        # pyrefly: ignore [missing-import]
        import httpx
        r = httpx.post(
            f"{API_BASE}/api/v1/submit/file",
            files={"file": (filename, file_bytes, "text/plain")},
            data={"language": language}, timeout=15,
        )
        return r.json()
    except Exception:
        code = file_bytes.decode("utf-8", errors="replace")
        return _local_submit(code, language, filename)


def api_status(session_id: str) -> dict:
    try:
        # pyrefly: ignore [missing-import]
        import httpx
        r = httpx.get(f"{API_BASE}/api/v1/status/{session_id}", timeout=5)
        return r.json()
    except Exception:
        # Find in local session store
        for s in st.session_state.sessions:
            if s["session_id"] == session_id:
                return s
        return {"error": "Session not found"}

def api_rag_query(question: str) -> dict:
    try:
        # pyrefly: ignore [missing-import]
        import httpx
        r = httpx.post(f"{API_BASE}/api/v1/rag/query", json={"question": question, "top_k": 3}, timeout=120)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Local (no-API) validators & submit — runs fully in-browser
# ─────────────────────────────────────────────────────────────────────────────
def _detect_language(code: str, filename: str = "") -> str:
    from app.utils.language_detector import detect_language
    return detect_language(code, filename).value


def _local_validate(code: str, language: str) -> dict:
    from app.utils.code_validator import validate_code
    from app.models.session import Language
    
    if not code.strip():
        return {"valid": False, "errors": [{"field": "code", "message": "Code is empty."}], "detail": "Empty submission."}
        
    try:
        lang_enum = Language(language)
    except ValueError:
        lang_enum = Language.python
        
    result = validate_code(code, lang_enum)
    return {
        "valid": result.valid,
        "errors": [{"field": e.field, "message": e.message, "line": e.line} for e in result.errors],
        "detail": result.detail
    }


def _local_submit(code: str, language: str, filename: str = "") -> dict:
    if language == "auto":
        language = _detect_language(code, filename)

    val = _local_validate(code, language)
    if not val["valid"]:
        return {"detail": {"message": "Validation failed", "errors": val["errors"]}}

    session_id = str(uuid.uuid4())
    loc = len(code.splitlines())
    session = {
        "session_id": session_id,
        "status": "queued",
        "language": language,
        "filename": filename or "untitled",
        "lines_of_code": loc,
        "estimated_seconds": max(30, min(loc // 10, 120)),
        "submitted_at": datetime.utcnow().isoformat(),
        "progress_pct": 0,
        "current_stage": "Waiting for agent pipeline (Milestone 3)",
        "message": "Code submitted (local mode — backend not running). Analysis pipeline coming in Milestone 3.",
        "code_preview": code[:500],
    }
    st.session_state.sessions.insert(0, session)
    return session


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 AI Code Review Agent")
    st.markdown("*Group 2 — Milestone 1*")
    st.markdown("---")

    # Language selector
    st.markdown("### ⚙️ Settings")
    language_choice = st.selectbox(
        "Language",
        ["auto", "python", "java"],
        index=0,
        help="Auto-detect or manually specify the programming language.",
    )

    st.markdown("---")

    # System Status
    st.markdown("### 🖥️ System Status")
    api_ok = check_api()
    if api_ok:
        st.markdown('<span class="badge badge-ok">✅ API Online</span>', unsafe_allow_html=True)
        st.session_state.api_mode = "api"
    else:
        st.markdown('<span class="badge badge-medium">⚡ Local Mode</span>', unsafe_allow_html=True)
        st.caption("FastAPI not running. Using browser-local validation. Start with: `uvicorn app.main:app --reload`")
        st.session_state.api_mode = "local"

    st.markdown("---")

    # Milestone progress
    st.markdown("### 📅 Milestone Progress")
    milestones = [
        ("M1", "Foundation, Code Submit & RAG Knowledge Base", True),
        ("M2", "Multi-Agent Pipeline & Orchestration", False),
        ("M3", "Findings Display & Severity Scoring", False),
        ("M4", "Conversational Code Assistant Interface", False),
        ("M5", "Code Review Report Generation & Export", False),
        ("M6", "Production Hardening", False),
    ]
    for tag, name, done in milestones:
        icon = "✅" if done else "🔄"
        color = "#10b981" if done else "#475569"
        st.markdown(f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0;color:{color};font-size:13px">'
                    f'<span>{icon}</span><span><b>{tag}</b> — {name}</span></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📦 Stack")
    st.caption("FastAPI · Streamlit · Ollama · ChromaDB · LangGraph · Celery · Redis")
    st.caption("100% Open-Source · Local · Apple M4")


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>🔍 AI Code Review & Security Analysis Agent</h1>
  <p class="subtitle">Automated OWASP vulnerability detection · Code quality analysis · Intelligent remediation</p>
  <div class="badges">
    <span class="badge badge-info">🐍 Python</span>
    <span class="badge badge-info">☕ Java</span>
    <span class="badge badge-critical">🛡️ OWASP Top-10</span>
    <span class="badge badge-low">✅ Milestone 1</span>
  </div>
</div>
""", unsafe_allow_html=True)

# Mode banner
mode = st.session_state.api_mode
if mode == "local":
    st.info("⚡ **Local Mode** — Validation runs in-browser. Start `uvicorn app.main:app --reload` for the full API experience.", icon="ℹ️")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────
tab_paste, tab_upload, tab_history, tab_chat, tab_about = st.tabs([
    "📋  Paste Code",
    "📁  Upload File",
    "📜  Session History",
    "💬  Ask Assistant",
    "ℹ️  About",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Paste Code
# ══════════════════════════════════════════════════════════════════════════════
with tab_paste:
    st.markdown("### Paste Your Source Code")
    st.markdown("Enter Python or Java code below. Language is auto-detected. The system validates syntax and queues a full analysis.")

    # Code editor — try streamlit-ace, fallback to text_area
    editor_lang = "python" if language_choice in ["python", "auto"] else "java"
    try:
        # pyrefly: ignore [missing-import]
        from streamlit_ace import st_ace
        code_input = st_ace(
            placeholder="# Paste your Python or Java code here...\n\ndef example():\n    user_id = input('Enter ID: ')\n    query = f'SELECT * FROM users WHERE id={user_id}'  # SQL injection!",
            language=editor_lang,
            theme="monokai",
            key="ace_editor",
            height=380,
            font_size=13,
            show_gutter=True,
            show_print_margin=False,
            wrap=False,
            auto_update=True,
        )
        st.caption("💡 Monaco-style editor — syntax highlighted, line numbers enabled.")
    except Exception:
        code_input = st.text_area(
            "Source Code",
            placeholder="# Paste your Python or Java code here...\n\ndef example():\n    user_id = input('Enter ID: ')\n    query = f'SELECT * FROM users WHERE id={user_id}'  # SQL injection!",
            height=350,
            key="code_textarea",
            label_visibility="collapsed",
        )

    # ── Live language detection + syntax check ──────────────────────────────
    if code_input and code_input.strip():
        lines = code_input.splitlines()
        detected = _detect_language(code_input) if language_choice == "auto" else language_choice

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Lines of Code", len(lines))
        col_m2.metric("Characters", len(code_input))
        col_m3.metric("Selected", language_choice.upper())
        col_m4.metric("Detected As", detected.upper())

        # Auto-run local syntax check and show result immediately
        live_val = _local_validate(code_input, detected)
        if live_val["valid"]:
            st.markdown(f"""
            <div style="background:rgba(16,185,129,0.1);border:1px solid #10b981;border-radius:8px;
                        padding:10px 16px;margin:8px 0;display:flex;align-items:center;gap:10px">
              <span style="font-size:1.2rem">✅</span>
              <div>
                <b style="color:#10b981">No Syntax Errors</b>
                <span style="color:#94a3b8;font-size:13px;margin-left:10px">
                  Language: <b>{detected.upper()}</b> — {live_val.get('detail','')}
                </span>
              </div>
            </div>""", unsafe_allow_html=True)
        else:
            error_count = len(live_val.get("errors", []))
            st.markdown(f"""
            <div style="background:rgba(239,68,68,0.1);border:1px solid #ef4444;border-radius:8px;
                        padding:10px 16px;margin:8px 0">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                <span style="font-size:1.2rem">❌</span>
                <b style="color:#ef4444">Syntax Error{'s' if error_count > 1 else ''} Found ({error_count})</b>
                <span style="color:#94a3b8;font-size:13px;margin-left:6px">Language: <b>{detected.upper()}</b></span>
              </div>""", unsafe_allow_html=True)
            for err in live_val.get("errors", []):
                msg = err.get("message", "")
                line_no = err.get("line")
                location = f"Line {line_no} → " if line_no else ""
                st.markdown(f"""
              <div style="background:rgba(0,0,0,0.3);border-left:3px solid #ef4444;
                          padding:6px 12px;margin:4px 0;border-radius:0 6px 6px 0;font-family:monospace">
                <span style="color:#fca5a5">{location}{msg}</span>
              </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # ── Action buttons ────────────────────────────────────────────────────────
    st.markdown(" ")
    col_v, col_a, col_clear = st.columns([1.2, 1.5, 4])

    with col_v:
        validate_btn = st.button("✔️ Re-validate Syntax", key="validate_paste_btn")
    with col_a:
        analyze_btn = st.button("🚀 Submit for Analysis", key="analyze_paste_btn", type="primary")
    with col_clear:
        pass

    # Manual re-validate (calls API for detailed server-side validation)
    if validate_btn:
        if not code_input or not code_input.strip():
            st.warning("⚠️ Please enter some code first.")
        else:
            with st.spinner("Validating syntax..."):
                result = api_validate(code_input, language_choice)

            if result.get("valid"):
                st.markdown(f"""
                <div class="glass-card glass-card-green">
                  <b>✅ Syntax Valid</b><br>
                  <span style="color:#94a3b8">{result.get('detail','')}</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="glass-card glass-card-red">
                  <b>❌ Syntax Error</b><br>
                  <span style="color:#94a3b8">{result.get('detail','')}</span>
                </div>""", unsafe_allow_html=True)
                for err in result.get("errors", []):
                    st.code(err.get("message", ""), language="text")

    # Submit for Analysis
    if analyze_btn:
        if not code_input or not code_input.strip():
            st.warning("⚠️ Please enter some code before submitting.")
        else:
            with st.spinner("Submitting code for analysis..."):
                response = api_submit_paste(code_input, language_choice)

            # Check for validation error from API
            if isinstance(response.get("detail"), dict):
                st.error("❌ Submission failed — validation errors:")
                for err in response["detail"].get("errors", []):
                    st.code(err.get("message", ""), language="text")
            elif response.get("error"):
                st.error(f"❌ {response['error']}")
            else:
                sid = response.get("session_id", "N/A")
                lang = response.get("language", language_choice)
                loc = response.get("lines_of_code", len(code_input.splitlines()))
                est = response.get("estimated_seconds", 45)
                msg = response.get("message", "Queued.")
                status_val = response.get("status", "queued")

                status_badge = {
                    "queued": '<span class="badge badge-medium">⏳ Queued</span>',
                    "running": '<span class="badge badge-info">🔵 Running</span>',
                    "completed": '<span class="badge badge-ok">✅ Completed</span>',
                    "failed": '<span class="badge badge-critical">❌ Failed</span>',
                }.get(status_val, f'<span class="badge badge-medium">{status_val.capitalize()}</span>')

                st.markdown(f"""
                <div class="glass-card glass-card-blue">
                  <h4 style="margin:0 0 12px;color:#a5b4fc">✅ Code Submitted Successfully</h4>
                  <table style="width:100%;border-collapse:collapse">
                    <tr><td style="color:#64748b;padding:4px 12px 4px 0;width:140px">Session ID</td>
                        <td><code style="font-size:12px">{sid}</code></td></tr>
                    <tr><td style="color:#64748b;padding:4px 12px 4px 0">Language</td>
                        <td><span class="badge badge-info">{lang.upper()}</span></td></tr>
                    <tr><td style="color:#64748b;padding:4px 12px 4px 0">Lines of Code</td>
                        <td style="color:#e2e8f0">{loc}</td></tr>
                    <tr><td style="color:#64748b;padding:4px 12px 4px 0">Est. Time</td>
                        <td style="color:#e2e8f0">~{est}s</td></tr>
                    <tr><td style="color:#64748b;padding:4px 12px 4px 0">Status</td>
                        <td>{status_badge}</td></tr>
                  </table>
                  <p style="margin:12px 0 0;color:#475569;font-size:13px">{msg}</p>
                </div>
                """, unsafe_allow_html=True)

                if mode == "local":
                    st.info("💡 **Agent Pipeline** will be available in **Milestone 3**. Start the FastAPI backend (`uvicorn app.main:app --reload`) to connect to the full pipeline.", icon="🔄")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — File Upload
# ══════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.markdown("### Upload a Source File")
    st.markdown("Upload a `.py` or `.java` file for analysis. Max file size: **5 MB**. Max lines: **10,000**.")

    uploaded_file = st.file_uploader(
        "Drop your file here or click to browse",
        type=["py", "java"],
        key="file_uploader",
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        raw_bytes = uploaded_file.read()
        try:
            file_code = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            st.error("❌ File is not valid UTF-8 text.")
            file_code = None

        if file_code:
            file_lines = file_code.splitlines()
            file_size_kb = len(raw_bytes) / 1024
            detected_file_lang = _detect_language(file_code, uploaded_file.name)

            # ── File info metrics ─────────────────────────────────────────────
            col_fi1, col_fi2, col_fi3, col_fi4 = st.columns(4)
            col_fi1.metric("File", uploaded_file.name)
            col_fi2.metric("Size", f"{file_size_kb:.1f} KB")
            col_fi3.metric("Lines", len(file_lines))
            col_fi4.metric("Detected Language", detected_file_lang.upper())

            # ── Live syntax validation result ─────────────────────────────────
            val_res = _local_validate(file_code, detected_file_lang)
            if val_res["valid"]:
                st.markdown(f"""
                <div style="background:rgba(16,185,129,0.1);border:1px solid #10b981;border-radius:8px;
                            padding:10px 16px;margin:8px 0;display:flex;align-items:center;gap:10px">
                  <span style="font-size:1.2rem">✅</span>
                  <div>
                    <b style="color:#10b981">No Syntax Errors</b>
                    <span style="color:#94a3b8;font-size:13px;margin-left:10px">
                      Language: <b>{detected_file_lang.upper()}</b> — {val_res.get('detail','')}
                    </span>
                  </div>
                </div>""", unsafe_allow_html=True)
            else:
                error_count = len(val_res.get("errors", []))
                st.markdown(f"""
                <div style="background:rgba(239,68,68,0.1);border:1px solid #ef4444;border-radius:8px;
                            padding:10px 16px;margin:8px 0">
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                    <span style="font-size:1.2rem">❌</span>
                    <b style="color:#ef4444">Syntax Error{'s' if error_count > 1 else ''} Found ({error_count})</b>
                    <span style="color:#94a3b8;font-size:13px;margin-left:6px">Language: <b>{detected_file_lang.upper()}</b></span>
                  </div>""", unsafe_allow_html=True)
                for err in val_res.get("errors", []):
                    msg = err.get("message", "")
                    line_no = err.get("line")
                    location = f"Line {line_no} → " if line_no else ""
                    st.markdown(f"""
                  <div style="background:rgba(0,0,0,0.3);border-left:3px solid #ef4444;
                              padding:6px 12px;margin:4px 0;border-radius:0 6px 6px 0;font-family:monospace">
                    <span style="color:#fca5a5">{location}{msg}</span>
                  </div>""", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # Code preview
            with st.expander("👁️ Preview file contents", expanded=False):
                preview = "\n".join(file_lines[:60])
                if len(file_lines) > 60:
                    preview += f"\n\n# ... {len(file_lines) - 60} more lines ..."
                st.code(preview, language=detected_file_lang)

            # Size limit check
            if len(file_lines) > 10000:
                st.error(f"❌ File has {len(file_lines):,} lines — exceeds 10,000 line limit.")
            elif file_size_kb > 5120:
                st.error("❌ File size exceeds 5 MB limit.")
            else:
                st.markdown(" ")
                upload_col, _ = st.columns([1, 3])
                with upload_col:
                    upload_btn = st.button("🚀 Submit File for Analysis", key="upload_submit_btn", type="primary")

                if upload_btn:
                    lang_to_use = language_choice if language_choice != "auto" else detected_file_lang
                    with st.spinner(f"Uploading `{uploaded_file.name}`..."):
                        response = api_submit_file(raw_bytes, uploaded_file.name, lang_to_use)

                    if isinstance(response.get("detail"), dict):
                        st.error("❌ Validation failed:")
                        for err in response["detail"].get("errors", []):
                            st.code(err["message"], language="text")
                    elif response.get("error"):
                        st.error(f"❌ {response['error']}")
                    else:
                        sid = response.get("session_id", "N/A")
                        st.markdown(f"""
                        <div class="glass-card glass-card-blue">
                          <h4 style="margin:0 0 10px;color:#a5b4fc">✅ File Submitted</h4>
                          <p style="margin:4px 0;color:#94a3b8"><b>Session:</b> <code>{sid}</code></p>
                          <p style="margin:4px 0;color:#94a3b8"><b>File:</b> {uploaded_file.name}</p>
                          <p style="margin:4px 0;color:#94a3b8"><b>Language:</b> {lang_to_use.upper()}</p>
                          <p style="margin:4px 0;color:#94a3b8"><b>Lines:</b> {len(file_lines)}</p>
                        </div>
                        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center;padding:40px;color:#475569">
          <div style="font-size:3rem;margin-bottom:12px">📁</div>
          <p>Drag & drop a <b>.py</b> or <b>.java</b> file above</p>
          <p style="font-size:13px">Supported: Python (.py) and Java (.java) source files</p>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Session History
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.markdown("### 📜 Session History")

    sessions = st.session_state.get("sessions", [])

    if sessions:
        col_hist_r, col_hist_c = st.columns([1, 4])
        with col_hist_r:
            if st.button("🗑️ Clear History", key="clear_hist"):
                st.session_state.sessions = []
                st.rerun()

        for i, s in enumerate(sessions):
            sid = s.get("session_id", "?")
            status = s.get("status", "queued")
            lang = s.get("language", "?")
            filename = s.get("filename", "untitled")
            loc = s.get("lines_of_code", 0)
            ts = s.get("submitted_at", "")[:19].replace("T", " ")
            stage = s.get("current_stage", "queued")

            status_badge = {
                "queued": '<span class="badge badge-medium">⏳ Queued</span>',
                "running": '<span class="badge badge-info">🔵 Running</span>',
                "completed": '<span class="badge badge-ok">✅ Completed</span>',
                "failed": '<span class="badge badge-critical">❌ Failed</span>',
            }.get(status, f'<span class="badge badge-info">{status}</span>')

            with st.expander(f"#{i+1}  {filename}  —  {ts}  —  {lang.upper()}", expanded=(i == 0)):
                st.markdown(f"""
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:8px">
                  <div><small style="color:#64748b">Status</small><br>{status_badge}</div>
                  <div><small style="color:#64748b">Language</small><br>
                       <span class="badge badge-info">{lang.upper()}</span></div>
                  <div><small style="color:#64748b">Lines</small><br>
                       <span style="color:#e2e8f0;font-weight:600">{loc}</span></div>
                </div>
                <div style="margin:8px 0">
                  <small style="color:#64748b">Session ID</small><br>
                  <code style="font-size:11px">{sid}</code>
                </div>
                <div style="margin:8px 0">
                  <small style="color:#64748b">Stage</small><br>
                  <span style="color:#94a3b8;font-size:13px">{stage}</span>
                </div>
                """, unsafe_allow_html=True)

                if mode == "api":
                    col_act1, col_act2 = st.columns(2)
                    with col_act1:
                        if st.button(f"🔄 Refresh Status", key=f"refresh_{i}"):
                            fresh = api_status(sid)
                            st.json(fresh)
                    with col_act2:
                        # Only show "View Full Report" button
                        if st.button(f"📄 View Full Report", key=f"report_{i}"):
                            try:
                                # pyrefly: ignore [missing-import]
                                import httpx
                                res = httpx.get(f"{API_BASE}/api/v1/result/{sid}", timeout=5).json()
                                st.markdown("##### Analysis Result")
                                st.json(res)
                            except Exception as e:
                                st.error(f"Could not fetch result: {e}")
    else:
        st.markdown("""
        <div style="text-align:center;padding:60px;color:#475569">
          <div style="font-size:3rem;margin-bottom:12px">📭</div>
          <p>No sessions yet.</p>
          <p style="font-size:13px">Submit code in the <b>Paste Code</b> or <b>Upload File</b> tabs to get started.</p>
        </div>
        """, unsafe_allow_html=True)

    # Manual lookup
    st.markdown("---")
    st.markdown("#### 🔍 Manual Session Lookup")
    manual_sid = st.text_input(
        "Session ID",
        placeholder="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        key="manual_sid_input",
        label_visibility="collapsed",
    )
    if manual_sid.strip():
        col_lu1, col_lu2 = st.columns(2)
        with col_lu1:
            if st.button("Look Up Status", key="lookup_btn"):
                result = api_status(manual_sid.strip())
                st.json(result)
        with col_lu2:
            if st.button("📄 View Full Report", key="lookup_report_btn"):
                try:
                    # pyrefly: ignore [missing-import]
                    import httpx
                    res = httpx.get(f"{API_BASE}/api/v1/result/{manual_sid.strip()}", timeout=5).json()
                    st.markdown("##### Analysis Result")
                    st.json(res)
                except Exception as e:
                    st.error(f"Could not fetch result: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Ask Assistant
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown("### 💬 Conversational Code Assistant")
    st.markdown("Ask security questions directly to the RAG Knowledge Base. The AI will answer grounded in OWASP guidelines.")
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        
    # Display chat messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "sources" in msg and msg["sources"]:
                with st.expander("📚 View Sources"):
                    for i, src in enumerate(msg["sources"], 1):
                        st.markdown(f"**Source {i}** (Score: {src.get('score', 'N/A')}):")
                        st.caption(f"{src.get('text', '')[:300]}...")
                        st.divider()

    # Chat input
    if user_q := st.chat_input("E.g. What is the best way to prevent SQL Injection?"):
        # Add user message to UI immediately
        st.session_state.chat_history.append({"role": "user", "content": user_q})
        with st.chat_message("user"):
            st.markdown(user_q)
            
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Searching Knowledge Base (This may take a minute on cold start)..."):
                if mode == "local":
                    st.error("❌ RAG Assistant requires the FastAPI backend to be running (`uvicorn app.main:app --reload`).")
                else:
                    res = api_rag_query(user_q)
                    if "error" in res:
                        st.error(f"❌ Error communicating with RAG endpoint: {res['error']}")
                    else:
                        answer = res.get("answer", "No answer generated.")
                        sources = res.get("sources", [])
                        st.markdown(answer)
                        if sources:
                            with st.expander("📚 View Sources"):
                                for i, src in enumerate(sources, 1):
                                    st.markdown(f"**Source {i}**:")
                                    st.caption(f"{src.get('text', '')[:300]}...")
                                    st.divider()
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": answer,
                            "sources": sources
                        })

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — About
# ══════════════════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown("### About This Project")

    col_ab1, col_ab2 = st.columns(2)

    with col_ab1:
        st.markdown("""
        <div class="glass-card">
          <h4 style="color:#a5b4fc;margin-top:0">🎯 What This Does</h4>
          <p>An AI-powered platform that automatically analyzes Python and Java source code for:</p>
          <ul style="color:#94a3b8;line-height:2">
            <li>🛡️ OWASP Top-10 security vulnerabilities</li>
            <li>🔍 Code smells & design anti-patterns</li>
            <li>📊 Cyclomatic complexity & maintainability</li>
            <li>🔧 Corrected code & remediation guidance</li>
            <li>💬 RAG-powered secure coding Q&A</li>
          </ul>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="glass-card">
          <h4 style="color:#a5b4fc;margin-top:0">🤖 Five AI Agents</h4>
          <ul style="color:#94a3b8;line-height:2">
            <li><b style="color:#e2e8f0">Code Analysis Agent</b> — smells, complexity, design</li>
            <li><b style="color:#e2e8f0">Security Vulnerability Agent</b> — OWASP A01–A10</li>
            <li><b style="color:#e2e8f0">Remediation Agent</b> — corrected code examples</li>
            <li><b style="color:#e2e8f0">PR Summary Agent</b> — structured review</li>
            <li><b style="color:#e2e8f0">Conversational Assistant</b> — RAG-powered Q&A</li>
          </ul>
        </div>
        """, unsafe_allow_html=True)

    with col_ab2:
        st.markdown("""
        <div class="glass-card">
          <h4 style="color:#a5b4fc;margin-top:0">🛠️ Tech Stack</h4>
          <table style="width:100%;border-collapse:collapse;color:#94a3b8;font-size:13px">
            <tr><td style="padding:6px 0;color:#64748b">LLM</td><td>Ollama (codestral, qwen2.5-coder)</td></tr>
            <tr><td style="padding:6px 0;color:#64748b">Embeddings</td><td>nomic-embed-text (768-dim)</td></tr>
            <tr><td style="padding:6px 0;color:#64748b">Vector DB</td><td>ChromaDB (local persistent)</td></tr>
            <tr><td style="padding:6px 0;color:#64748b">RAG</td><td>LlamaIndex + BM25 + Reranker</td></tr>
            <tr><td style="padding:6px 0;color:#64748b">Agents</td><td>LangGraph (stateful DAG)</td></tr>
            <tr><td style="padding:6px 0;color:#64748b">Backend</td><td>FastAPI + Celery + Redis</td></tr>
            <tr><td style="padding:6px 0;color:#64748b">Frontend</td><td>Streamlit + streamlit-ace</td></tr>
            <tr><td style="padding:6px 0;color:#64748b">Security Lint</td><td>Bandit + Semgrep + PMD</td></tr>
            <tr><td style="padding:6px 0;color:#64748b">Monitoring</td><td>Prometheus + Grafana</td></tr>
          </table>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="glass-card">
          <h4 style="color:#a5b4fc;margin-top:0">📅 Milestone Status</h4>
          <div style="color:#94a3b8;font-size:13px;line-height:2.2">
            <div>✅ <b style="color:#10b981">M1</b> Foundation + Code Submission</div>
            <div>🔄 <b style="color:#f59e0b">M2</b> OWASP Knowledge Base + RAG</div>
            <div>📋 <b style="color:#475569">M3</b> Multi-Agent Pipeline</div>
            <div>📋 <b style="color:#475569">M4</b> Conversational UI</div>
            <div>📋 <b style="color:#475569">M5</b> Performance & Monitoring</div>
            <div>📋 <b style="color:#475569">M6</b> Production Hardening</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style="text-align:center;padding:16px;color:#475569;font-size:13px">
      <b>Group 2</b> · AI Code Review & Security Analysis Agent ·
      <a href="https://github.com/shubham0915/AI-Code-Review-Security-Analysis-Agent-Group2"
         style="color:#6366f1;text-decoration:none">GitHub Repository</a><br>
      100% Open-Source · Zero Cloud Cost · Runs locally on Apple M4
    </div>
    """, unsafe_allow_html=True)
