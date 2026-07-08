"""
frontend/app.py — Streamlit Developer Portal

Milestone 1 focus: Code Submission Module with:
  - Direct code paste (streamlit-ace Monaco-like editor)
  - File upload (.py / .java)
  - Language auto-detection
  - Syntax validation feedback
  - Session status polling
"""
from __future__ import annotations

import time
import httpx
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Page config — must be first Streamlit call
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Code Review Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "http://localhost:8000"

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS — dark glassmorphism theme
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  html, body, [class*="css"] {
      font-family: 'Inter', sans-serif;
  }

  /* Dark background */
  .stApp {
      background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #0d1b2a 100%);
      color: #e2e8f0;
  }

  /* Sidebar */
  section[data-testid="stSidebar"] {
      background: rgba(255,255,255,0.04);
      border-right: 1px solid rgba(255,255,255,0.08);
  }

  /* Cards */
  .glass-card {
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 16px;
      padding: 24px;
      margin: 12px 0;
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
  }

  /* Severity badges */
  .badge-critical { background:#7f1d1d; color:#fca5a5; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:600; }
  .badge-high     { background:#7c2d12; color:#fdba74; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:600; }
  .badge-medium   { background:#713f12; color:#fde68a; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:600; }
  .badge-low      { background:#064e3b; color:#6ee7b7; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:600; }
  .badge-info     { background:#1e3a5f; color:#93c5fd; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:600; }

  /* Score ring placeholder */
  .score-box {
      text-align: center;
      padding: 20px;
      border-radius: 12px;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
  }
  .score-number {
      font-size: 48px;
      font-weight: 700;
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
  }

  /* Buttons */
  .stButton > button {
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
      color: white !important;
      border: none !important;
      border-radius: 10px !important;
      font-weight: 600 !important;
      padding: 0.6rem 1.5rem !important;
      transition: all 0.2s ease !important;
  }
  .stButton > button:hover {
      transform: translateY(-1px) !important;
      box-shadow: 0 4px 20px rgba(99,102,241,0.4) !important;
  }

  /* Code editor area */
  .stTextArea textarea {
      font-family: 'JetBrains Mono', monospace !important;
      font-size: 13px !important;
      background: #0d1117 !important;
      color: #c9d1d9 !important;
      border: 1px solid rgba(255,255,255,0.15) !important;
      border-radius: 10px !important;
  }

  /* Tabs */
  .stTabs [data-baseweb="tab-list"] {
      background: rgba(255,255,255,0.04);
      border-radius: 10px;
      padding: 4px;
  }
  .stTabs [data-baseweb="tab"] {
      border-radius: 8px;
      color: #94a3b8;
  }
  .stTabs [aria-selected="true"] {
      background: rgba(99,102,241,0.2) !important;
      color: #a5b4fc !important;
  }

  /* Header */
  .main-header {
      text-align: center;
      padding: 32px 0 16px;
  }
  .main-header h1 {
      font-size: 2.4rem;
      font-weight: 700;
      background: linear-gradient(135deg, #6366f1 0%, #a78bfa 50%, #38bdf8 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 8px;
  }
  .main-header p {
      color: #64748b;
      font-size: 1rem;
  }

  hr { border-color: rgba(255,255,255,0.08) !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────────────────────────────────────
def api_submit_paste(code: str, language: str, filename: str = "") -> dict:
    payload = {"code": code, "language": language}
    if filename:
        payload["filename"] = filename
    try:
        resp = httpx.post(f"{API_BASE}/api/v1/submit/paste", json=payload, timeout=30)
        return resp.json()
    except httpx.ConnectError:
        return {"error": "Cannot connect to API. Is the backend running?"}
    except Exception as e:
        return {"error": str(e)}


def api_submit_file(file_bytes: bytes, filename: str, language: str) -> dict:
    try:
        resp = httpx.post(
            f"{API_BASE}/api/v1/submit/file",
            files={"file": (filename, file_bytes, "text/plain")},
            data={"language": language},
            timeout=30,
        )
        return resp.json()
    except httpx.ConnectError:
        return {"error": "Cannot connect to API. Is the backend running?"}
    except Exception as e:
        return {"error": str(e)}


def api_validate(code: str, language: str) -> dict:
    payload = {"code": code, "language": language}
    try:
        resp = httpx.post(f"{API_BASE}/api/v1/submit/validate", json=payload, timeout=10)
        return resp.json()
    except httpx.ConnectError:
        return {"error": "Cannot connect to API."}
    except Exception as e:
        return {"error": str(e)}


def api_status(session_id: str) -> dict:
    try:
        resp = httpx.get(f"{API_BASE}/api/v1/status/{session_id}", timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def api_health() -> dict:
    try:
        resp = httpx.get(f"{API_BASE}/health/ready", timeout=5)
        return resp.json()
    except Exception:
        return {"ready": False, "checks": {"api": "unreachable"}}


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    language_choice = st.selectbox(
        "Language",
        ["auto", "python", "java"],
        index=0,
        help="Select the programming language or let the system auto-detect.",
    )

    st.markdown("---")
    st.markdown("### 🖥️ System Status")
    if st.button("Check Backend", key="health_btn"):
        health = api_health()
        if health.get("ready"):
            st.success("✅ All systems operational")
            for svc, s in health.get("checks", {}).items():
                st.markdown(f"- **{svc}**: {s}")
        else:
            st.error("❌ Some services are down")
            for svc, s in health.get("checks", {}).items():
                icon = "✅" if s == "ok" else "❌"
                st.markdown(f"- {icon} **{svc}**: {s}")

    st.markdown("---")
    st.markdown("### 📊 Milestone Progress")
    st.progress(1/6, text="Milestone 1/6: Foundation")
    st.markdown("""
    - ✅ Project skeleton
    - ✅ Code Submission Module
    - ✅ FastAPI backend
    - ✅ Redis + Docker
    - 🔄 Knowledge Base (M2)
    - 🔄 Agent Pipeline (M3)
    """)

    st.markdown("---")
    st.caption("AI Code Review & Security Analysis Agent v1.0")
    st.caption("100% Open-Source · Local · Apple M4 Ready")


# ─────────────────────────────────────────────────────────────────────────────
# Main header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>🔍 AI Code Review & Security Analysis Agent</h1>
  <p>Automated OWASP vulnerability detection, code quality analysis, and intelligent remediation</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Main tabs
# ─────────────────────────────────────────────────────────────────────────────
tab_paste, tab_upload, tab_history = st.tabs([
    "📋 Paste Code",
    "📁 Upload File",
    "📜 Session History",
])

# ── TAB 1: Paste Code ────────────────────────────────────────────────────────
with tab_paste:
    st.markdown("### Paste Your Source Code")
    st.markdown(
        "Paste Python or Java code below. The system will auto-detect the language "
        "and queue a full security + quality analysis."
    )

    # Try streamlit-ace for Monaco-like editor, fallback to text_area
    try:
        from streamlit_ace import st_ace
        code_input = st_ace(
            placeholder="# Paste your Python or Java code here...",
            language="python" if language_choice in ["python", "auto"] else "java",
            theme="monokai",
            key="ace_editor",
            height=400,
            font_size=13,
            show_gutter=True,
            show_print_margin=False,
            auto_update=False,
        )
    except ImportError:
        code_input = st.text_area(
            "Source Code",
            placeholder="# Paste your Python or Java code here...\n\ndef example():\n    pass",
            height=350,
            key="code_textarea",
        )

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        validate_btn = st.button("✔️ Validate Syntax", key="validate_paste_btn")
    with col2:
        analyze_btn = st.button("🚀 Run Analysis", key="analyze_paste_btn", type="primary")

    # Validate only
    if validate_btn and code_input:
        with st.spinner("Validating syntax..."):
            result = api_validate(code_input, language_choice)
        if result.get("error"):
            st.error(f"API Error: {result['error']}")
        elif result.get("valid"):
            st.success(f"✅ {result.get('detail', 'Syntax is valid.')}")
        else:
            st.error(f"❌ {result.get('detail', 'Syntax errors found.')}")
            for err in result.get("errors", []):
                st.code(err.get("message", ""), language="text")

    # Full analysis
    if analyze_btn and code_input:
        with st.spinner("Submitting code for analysis..."):
            response = api_submit_paste(code_input, language_choice)

        if response.get("error"):
            st.error(f"❌ {response['error']}")
        elif "detail" in response and isinstance(response["detail"], dict):
            st.error("❌ Validation failed:")
            for err in response["detail"].get("errors", []):
                st.code(err.get("message", ""), language="text")
        else:
            session_id = response.get("session_id")
            st.session_state["last_session_id"] = session_id

            st.markdown(f"""
            <div class="glass-card">
              <h4>✅ Analysis Queued Successfully</h4>
              <p><strong>Session ID:</strong> <code>{session_id}</code></p>
              <p><strong>Language:</strong> {response.get('language', 'auto')}</p>
              <p><strong>Lines of Code:</strong> {response.get('lines_of_code', 0)}</p>
              <p><strong>Estimated Time:</strong> ~{response.get('estimated_seconds', 45)}s</p>
              <p>{response.get('message', '')}</p>
            </div>
            """, unsafe_allow_html=True)

            # Poll status
            if session_id:
                with st.spinner("Waiting for analysis to complete..."):
                    for _ in range(30):
                        time.sleep(3)
                        status_resp = api_status(session_id)
                        current_status = status_resp.get("status", "queued")
                        if current_status == "completed":
                            st.success("✅ Analysis complete! Check Session History tab.")
                            break
                        elif current_status == "failed":
                            st.error(f"❌ Analysis failed: {status_resp.get('error_message', '')}")
                            break
                    else:
                        st.info("⏳ Analysis still running. Check the Session History tab for results.")

    elif analyze_btn and not code_input:
        st.warning("⚠️ Please enter some code before running analysis.")

# ── TAB 2: File Upload ───────────────────────────────────────────────────────
with tab_upload:
    st.markdown("### Upload a Source File")
    st.markdown("Upload a `.py` or `.java` file (max 5 MB).")

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["py", "java"],
        key="file_uploader",
        help="Only .py (Python) and .java (Java) files are supported.",
    )

    if uploaded_file:
        st.markdown(f"**File:** `{uploaded_file.name}` | **Size:** {uploaded_file.size / 1024:.1f} KB")

        # Preview
        preview_code = uploaded_file.read().decode("utf-8", errors="replace")
        uploaded_file.seek(0)
        with st.expander("👁️ Preview file contents", expanded=False):
            lines = preview_code.splitlines()
            preview_lines = "\n".join(lines[:50])
            if len(lines) > 50:
                preview_lines += f"\n... ({len(lines) - 50} more lines)"
            st.code(preview_lines, language=language_choice if language_choice != "auto" else "python")

        col_a, col_b = st.columns([1, 3])
        with col_a:
            upload_btn = st.button("🚀 Analyze File", key="analyze_file_btn", type="primary")

        if upload_btn:
            file_bytes = uploaded_file.read()
            with st.spinner(f"Uploading and queuing `{uploaded_file.name}`..."):
                response = api_submit_file(file_bytes, uploaded_file.name, language_choice)

            if response.get("error"):
                st.error(f"❌ {response['error']}")
            else:
                session_id = response.get("session_id")
                st.session_state["last_session_id"] = session_id
                st.success(f"✅ File queued! Session ID: `{session_id}`")
                st.json(response)

# ── TAB 3: Session History ───────────────────────────────────────────────────
with tab_history:
    st.markdown("### Session History")

    last_sid = st.session_state.get("last_session_id")
    if last_sid:
        st.markdown(f"**Last Session ID:** `{last_sid}`")

        col_refresh, _ = st.columns([1, 3])
        with col_refresh:
            refresh_btn = st.button("🔄 Refresh Status", key="refresh_btn")

        if refresh_btn or True:
            status_resp = api_status(last_sid)
            current_status = status_resp.get("status", "unknown")

            status_colors = {
                "queued": "🟡",
                "running": "🔵",
                "completed": "🟢",
                "failed": "🔴",
            }
            icon = status_colors.get(current_status, "⚪")

            st.markdown(f"""
            <div class="glass-card">
              <h4>{icon} Analysis Status</h4>
              <p><strong>Session:</strong> <code>{last_sid}</code></p>
              <p><strong>Status:</strong> {current_status.upper()}</p>
              <p><strong>Progress:</strong> {status_resp.get('progress_pct', 0)}%</p>
              <p><strong>Stage:</strong> {status_resp.get('current_stage', 'N/A')}</p>
            </div>
            """, unsafe_allow_html=True)

            if current_status == "completed":
                st.info("🎯 Analysis complete! Results will be available in the Results tab once agents are implemented (Milestone 3).")
    else:
        st.info("No sessions yet. Submit code in the 'Paste Code' or 'Upload File' tabs.")

    st.markdown("---")
    st.markdown("#### 📝 Manual Session Lookup")
    manual_sid = st.text_input("Enter Session ID", placeholder="3fa85f64-5717-4562-b3fc-2c963f66afa6", key="manual_sid")
    if st.button("Look Up", key="lookup_btn") and manual_sid:
        result = api_status(manual_sid.strip())
        st.json(result)
