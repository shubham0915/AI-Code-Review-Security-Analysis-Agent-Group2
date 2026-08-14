"""
About this file: app.py
Structure: Single-page application with Submit & Analyze tab and About tab.
           Results render inline (no modals, no session history tab).
           Includes 4 Plotly charts, inline issue cards, and JSON download.
Methods used: check_api, api_validate, api_submit_paste, api_submit_file,
              api_status, api_rag_query, api_chat, render_results, render_charts.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
import streamlit as st
import logfire
from dotenv import load_dotenv

load_dotenv(override=True)
logfire.configure()
logfire.instrument_httpx()

st.set_page_config(
    page_title="AI Code Review Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/shubham0915/AI-Code-Review-Security-Analysis-Agent-Group2",
        "Report a bug": "https://github.com/shubham0915/AI-Code-Review-Security-Analysis-Agent-Group2/issues",
        "About": "AI Code Review & Security Analysis Agent — Group 2",
    },
)

API_BASE = "http://localhost:8000"

# ══════════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM — Premium dark glassmorphism
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Background ── */
.stApp {
    background: linear-gradient(135deg, #060818 0%, #0a0f1e 45%, #080c1a 100%);
    color: #e2e8f0;
    min-height: 100vh;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(15,20,40,0.98) 0%, rgba(10,15,35,0.98) 100%) !important;
    border-right: 1px solid rgba(99,102,241,0.15) !important;
}
section[data-testid="stSidebar"] .stMarkdown { color: #94a3b8; }
section[data-testid="stSidebar"] .stSelectbox label { color: #94a3b8 !important; }

/* ── Main content ── */
.main .block-container {
    padding-top: 1rem;
    padding-bottom: 4rem;
    max-width: 1400px;
}

/* ── Hero header ── */
.hero {
    text-align: center;
    padding: 2rem 1rem 1.5rem;
    position: relative;
}
.hero::before {
    content: '';
    position: absolute;
    top: 0; left: 50%; transform: translateX(-50%);
    width: 600px; height: 200px;
    background: radial-gradient(ellipse, rgba(99,102,241,0.12) 0%, transparent 70%);
    pointer-events: none;
}
.hero h1 {
    font-size: 3rem; font-weight: 900; letter-spacing: -1px;
    background: linear-gradient(135deg, #818cf8 0%, #c4b5fd 40%, #38bdf8 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0 0 0.5rem;
}
.hero p {
    color: #64748b; font-size: 1.1rem; font-weight: 400; margin: 0;
}
.hero-badges { margin-top: 1rem; display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }

/* ── Badges ── */
.badge {
    display: inline-flex; align-items: center; gap: 4px;
    border-radius: 999px; padding: 4px 12px;
    font-size: 12px; font-weight: 600; letter-spacing: 0.02em;
}
.badge-critical { background: rgba(239,68,68,0.15); color: #fca5a5; border: 1px solid rgba(239,68,68,0.3); }
.badge-high     { background: rgba(249,115,22,0.15); color: #fdba74; border: 1px solid rgba(249,115,22,0.3); }
.badge-medium   { background: rgba(234,179,8,0.15);  color: #fde047; border: 1px solid rgba(234,179,8,0.3); }
.badge-low      { background: rgba(34,197,94,0.15);  color: #86efac; border: 1px solid rgba(34,197,94,0.3); }
.badge-info     { background: rgba(99,102,241,0.15); color: #a5b4fc; border: 1px solid rgba(99,102,241,0.3); }
.badge-ok       { background: rgba(16,185,129,0.15); color: #6ee7b7; border: 1px solid rgba(16,185,129,0.3); }
.badge-clean    { background: rgba(16,185,129,0.2);  color: #34d399; border: 1px solid rgba(16,185,129,0.4); }

/* ── Glass cards ── */
.glass-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 20px 24px;
    margin: 10px 0;
    backdrop-filter: blur(12px);
    transition: border-color 0.2s;
}
.glass-card:hover { border-color: rgba(99,102,241,0.25); }
.glass-card-green  { border-left: 3px solid #10b981 !important; }
.glass-card-red    { border-left: 3px solid #ef4444 !important; }
.glass-card-yellow { border-left: 3px solid #f59e0b !important; }
.glass-card-blue   { border-left: 3px solid #6366f1 !important; }
.glass-card-purple { border-left: 3px solid #a855f7 !important; }

/* ── Issue cards ── */
.issue-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 16px 20px;
    margin: 10px 0;
    transition: all 0.2s;
}
.issue-card:hover {
    background: rgba(255,255,255,0.055);
    border-color: rgba(255,255,255,0.14);
}
.issue-card-critical { border-left: 4px solid #ef4444; }
.issue-card-high     { border-left: 4px solid #f97316; }
.issue-card-medium   { border-left: 4px solid #eab308; }
.issue-card-low      { border-left: 4px solid #22c55e; }
.issue-card-info     { border-left: 4px solid #6366f1; }

.issue-title {
    font-size: 15px; font-weight: 700; color: #e2e8f0;
    margin: 0 0 6px; display: flex; align-items: center; gap: 8px;
}
.issue-meta {
    font-size: 12px; color: #64748b; margin-bottom: 8px;
}
.issue-desc { color: #94a3b8; font-size: 13px; line-height: 1.6; margin: 6px 0; }
.issue-fix-label {
    font-size: 12px; font-weight: 600; color: #10b981;
    text-transform: uppercase; letter-spacing: 0.06em; margin-top: 12px;
}

/* ── Risk banner ── */
.risk-banner {
    border-radius: 16px; padding: 20px 24px; margin: 16px 0;
    display: flex; align-items: center; justify-content: space-between;
}

/* ── Score cards ── */
.score-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0;
}
.score-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px; padding: 16px 20px; text-align: center;
}
.score-num {
    font-size: 2rem; font-weight: 800; line-height: 1;
    background: linear-gradient(135deg, #818cf8, #38bdf8);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.score-label { font-size: 12px; color: #64748b; margin-top: 4px; font-weight: 500; }

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    padding: 0.55rem 1.4rem !important; font-size: 0.9rem !important;
    transition: all 0.25s ease !important; letter-spacing: 0.01em !important;
    box-shadow: 0 4px 15px rgba(99,102,241,0.3) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(99,102,241,0.5) !important;
}
.stButton > button[kind="secondary"] {
    background: rgba(255,255,255,0.07) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    box-shadow: none !important;
}

/* ── Download button ── */
[data-testid="stDownloadButton"] button {
    background: linear-gradient(135deg, #059669, #10b981) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    box-shadow: 0 4px 15px rgba(16,185,129,0.3) !important;
    transition: all 0.25s !important;
}
[data-testid="stDownloadButton"] button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(16,185,129,0.5) !important;
}

/* ── Code editor ── */
.stTextArea textarea {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important; line-height: 1.65 !important;
    background: #0d1117 !important; color: #c9d1d9 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
}
.stTextArea textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.18) !important;
}

/* ── Selectbox ── */
.stSelectbox > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important; color: #e2e8f0 !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.03);
    border-radius: 12px; padding: 4px; gap: 4px;
    border: 1px solid rgba(255,255,255,0.06);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important; color: #475569 !important;
    font-weight: 600 !important; font-size: 14px !important;
    padding: 9px 22px !important; transition: all 0.2s !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(99,102,241,0.2) !important;
    color: #a5b4fc !important;
    box-shadow: 0 2px 8px rgba(99,102,241,0.2) !important;
}

/* ── Metric ── */
[data-testid="stMetricValue"] { color: #a5b4fc !important; font-size: 1.7rem !important; font-weight: 800 !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 12px !important; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: rgba(99,102,241,0.04) !important;
    border: 2px dashed rgba(99,102,241,0.35) !important;
    border-radius: 14px !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 8px !important; color: #94a3b8 !important;
    font-weight: 500 !important;
}

/* ── Divider ── */
hr { border-color: rgba(255,255,255,0.05) !important; }

/* ── Alerts ── */
.stAlert { border-radius: 10px !important; }

/* ── Code blocks ── */
code { background: rgba(99,102,241,0.12) !important; color: #c4b5fd !important; border-radius: 4px !important; }

/* ── Progress bar ── */
.stProgress > div > div { background: linear-gradient(90deg, #6366f1, #a855f7) !important; border-radius: 4px !important; }

/* ── Section heading ── */
.section-heading {
    font-size: 1.1rem; font-weight: 700; color: #e2e8f0;
    padding: 0 0 12px; border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 16px;
}
.section-sub { font-size: 13px; color: #64748b; margin-top: -8px; margin-bottom: 16px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for key, default in [
    ("api_mode", "checking"),
    ("last_result", None),
    ("last_session_id", None),
    ("polling", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ══════════════════════════════════════════════════════════════════════════════
# API HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def check_api() -> bool:
    try:
        import httpx
        return httpx.get(f"{API_BASE}/health", timeout=2).status_code == 200
    except Exception:
        return False


def api_validate(code: str, language: str) -> dict:
    try:
        import httpx
        r = httpx.post(f"{API_BASE}/api/v1/submit/validate",
                       json={"code": code, "language": language}, timeout=10)
        return r.json()
    except Exception:
        return _local_validate(code, language)


def api_submit_paste(code: str, language: str, filename: str = "") -> dict:
    try:
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
        import httpx
        return httpx.get(f"{API_BASE}/api/v1/status/{session_id}", timeout=5).json()
    except Exception:
        return {"error": "API unavailable"}


def api_fetch_result(session_id: str) -> dict:
    try:
        import httpx
        r = httpx.get(f"{API_BASE}/api/v1/result/{session_id}", timeout=10)
        if r.status_code != 200:
            return {"error": r.json().get("detail", f"HTTP {r.status_code} error")}
        return r.json()
    except Exception as e:
        return {"error": f"Could not fetch result: {e}"}


def api_rag_query(question: str) -> dict:
    try:
        import httpx
        r = httpx.post(f"{API_BASE}/api/v1/rag/query",
                       json={"question": question, "top_k": 3}, timeout=120)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def api_chat(session_id: str, message: str) -> dict:
    try:
        import httpx
        r = httpx.post(
            f"{API_BASE}/api/v1/chat",
            json={"session_id": session_id, "message": message, "thread_id": session_id},
            timeout=120
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# LOCAL FALLBACK HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _detect_language(code: str, filename: str = "") -> str:
    import os
    expected_lang = None
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".py":
            expected_lang = "python"
        elif ext == ".java":
            expected_lang = "java"
        elif ext in [".js", ".ts", ".html", ".css", ".cpp", ".c", ".go", ".rs", ".rb", ".php", ".sh", ".json"]:
            return "unsupported"

    try:
        from magika import Magika
        m = Magika()
        res = m.identify_bytes(code.encode("utf-8", errors="replace"))
        label = res.output.label.lower()
        if expected_lang and label not in ["txt", "empty", "unknown", expected_lang]:
            return f"mismatch|{expected_lang}|{label}"
        if label == "python": return "python"
        if label == "java": return "java"
        if label not in ["txt", "empty", "unknown", "python", "java"]:
            return "unsupported"
    except Exception:
        pass

    _JAVA_KW = ["public class", "private class", "public static void main", "import java.", "System.out."]
    _PY_KW   = ["def ", "__init__", "self.", "if __name__", "print(", "from __future__"]
    sample = code[:3000]
    j = sum(1 for k in _JAVA_KW if k in sample)
    p = sum(1 for k in _PY_KW if k in sample)
    if j > 0 and j >= p: return "java"
    if p > 0: return "python"
    return "unsupported"


def _local_validate(code: str, language: str) -> dict:
    if language.startswith("mismatch|"):
        _, expected, got = language.split("|")
        return {"valid": False,
                "errors": [{"field": "language",
                             "message": f"Extension Mismatch: File claims to be {expected.upper()}, but our AI detected {got.upper()}."}],
                "detail": "Content Mismatch."}
    if language == "unsupported":
        return {"valid": False,
                "errors": [{"field": "language",
                             "message": "Unsupported language. Please use Python or Java."}],
                "detail": "Language unsupported."}
    if language in ("python", "auto"):
        import ast
        try:
            ast.parse(code)
            return {"valid": True, "errors": [], "detail": "✅ Python syntax is valid."}
        except SyntaxError as e:
            return {"valid": False,
                    "errors": [{"field": "code", "message": f"SyntaxError at line {e.lineno}: {e.msg}", "line": e.lineno}],
                    "detail": "Syntax error."}
        except Exception as e:
            return {"valid": False, "errors": [{"field": "code", "message": str(e)}], "detail": "Validation error."}
    if language == "java":
        import re as _re
        errors = []
        try:
            import javalang
            try:
                javalang.parse.parse(code)
                return {"valid": True, "errors": [], "detail": "✅ Java syntax is valid."}
            except javalang.parser.JavaSyntaxError as e:
                line_no = e.at.position.line if e.at and e.at.position else None
                errors.append({"field": "code", "message": f"SyntaxError at line {line_no}: {e.description}", "line": line_no})
            except Exception:
                pass
        except ImportError:
            pass
        if not _re.search(r'\b(class|interface|enum)\s+\w+', code):
            errors.append({"field": "code", "message": "No class, interface, or enum declaration found."})
        if code.count("{") != code.count("}"):
            errors.append({"field": "code", "message": "Unbalanced braces."})
        if errors:
            return {"valid": False, "errors": errors, "detail": "Java validation failed."}
        return {"valid": True, "errors": [], "detail": "✅ Java heuristic pre-check passed."}
    return {"valid": True, "errors": [], "detail": "Pass-through."}


def _local_submit(code: str, language: str, filename: str = "") -> dict:
    if language == "auto":
        language = _detect_language(code, filename)
    val = _local_validate(code, language)
    if not val["valid"]:
        return {"detail": {"message": "Validation failed", "errors": val["errors"]}}
    session_id = str(uuid.uuid4())
    return {
        "session_id": session_id, "status": "local_mode",
        "language": language, "filename": filename or "untitled",
        "lines_of_code": len(code.splitlines()),
        "estimated_seconds": 45,
        "submitted_at": datetime.utcnow().isoformat(),
        "message": "Local mode — FastAPI backend not running.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# CHART RENDERER
# ══════════════════════════════════════════════════════════════════════════════
def render_charts(code_res: dict, sec_res: dict) -> None:
    """Renders 4 Plotly charts: severity donut, score comparison, OWASP category bar, complexity gauge."""
    import plotly.graph_objects as go

    vulns   = sec_res.get("vulnerabilities", [])
    findings = code_res.get("findings", [])

    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    CHART_BG    = "rgba(0,0,0,0)"
    PAPER_BG    = "rgba(0,0,0,0)"
    FONT_COLOR  = "#94a3b8"
    FONT_FAMILY = "Inter, sans-serif"
    BASE_LAYOUT = dict(
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=CHART_BG,
        font=dict(family=FONT_FAMILY, color=FONT_COLOR, size=12),
        margin=dict(l=0, r=0, t=40, b=0),
    )

    # ── Chart 1: Severity Distribution Donut ────────────────────────────────
    with col1:
        sev_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for v in vulns:
            s = str(v.get("severity", "")).capitalize()
            if s in sev_counts:
                sev_counts[s] += 1
        for f in findings:
            s = str(f.get("severity", "")).capitalize()
            if s in sev_counts:
                sev_counts[s] += 1

        total = sum(sev_counts.values())
        labels = list(sev_counts.keys())
        values = list(sev_counts.values())
        colors = ["#ef4444", "#f97316", "#eab308", "#22c55e"]

        fig1 = go.Figure(go.Pie(
            labels=labels, values=values,
            hole=0.6, marker=dict(colors=colors, line=dict(color="#0a0f1e", width=2)),
            textfont=dict(size=12, color="#e2e8f0"),
            hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Share: %{percent}<extra></extra>",
        ))
        fig1.add_annotation(
            text=f"<b>{total}</b><br><span style='font-size:10px'>Findings</span>",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color="#e2e8f0", family=FONT_FAMILY),
        )
        fig1.update_layout(**BASE_LAYOUT, title=dict(text="Severity Distribution", font=dict(size=14, color="#e2e8f0")),
                           showlegend=True,
                           legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5))
        st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

    # ── Chart 2: Security vs Quality Score ──────────────────────────────────
    with col2:
        q_score = code_res.get("quality_score", 0) or 0
        s_score = sec_res.get("security_score", 0) or 0

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            y=["Quality Score", "Security Score"],
            x=[q_score, s_score],
            orientation="h",
            marker=dict(
                color=[
                    "#6366f1" if q_score >= 70 else "#f97316" if q_score >= 40 else "#ef4444",
                    "#10b981" if s_score >= 70 else "#f97316" if s_score >= 40 else "#ef4444",
                ],
                line=dict(width=0),
            ),
            text=[f"{q_score}/100", f"{s_score}/100"],
            textposition="outside",
            textfont=dict(size=13, color="#e2e8f0"),
            hovertemplate="%{y}: <b>%{x}/100</b><extra></extra>",
        ))
        fig2.update_xaxes(range=[0, 110], showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                          zeroline=False, tickfont=dict(color="#64748b"))
        fig2.update_yaxes(showgrid=False, tickfont=dict(color="#94a3b8", size=12))
        fig2.update_layout(**BASE_LAYOUT,
                           title=dict(text="Quality vs Security Score", font=dict(size=14, color="#e2e8f0")),
                           bargap=0.4, height=220)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # ── Chart 3: Findings by OWASP Category ─────────────────────────────────
    with col3:
        cat_map: dict[str, int] = {}
        for v in vulns:
            cat = v.get("owasp_category", "Unknown")
            # Shorten label
            short = cat.split(" - ")[-1] if " - " in cat else cat
            cat_map[short] = cat_map.get(short, 0) + 1
        for f in findings:
            cat = f.get("category", "Code Quality").replace("_", " ").title()
            cat_map[cat] = cat_map.get(cat, 0) + 1

        if cat_map:
            sorted_cats = sorted(cat_map.items(), key=lambda x: x[1], reverse=True)[:8]
            cats, cnts = zip(*sorted_cats)
            palette = ["#818cf8", "#a78bfa", "#c4b5fd", "#7dd3fc", "#6ee7b7",
                       "#fde68a", "#fca5a5", "#f9a8d4"]
            fig3 = go.Figure(go.Bar(
                x=list(cnts), y=list(cats),
                orientation="h",
                marker=dict(color=palette[:len(cats)], line=dict(width=0)),
                text=list(cnts), textposition="outside",
                textfont=dict(size=12, color="#e2e8f0"),
                hovertemplate="%{y}: <b>%{x} finding(s)</b><extra></extra>",
            ))
            fig3.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                              zeroline=False, tickfont=dict(color="#64748b"))
            fig3.update_yaxes(showgrid=False, tickfont=dict(color="#94a3b8", size=11))
            fig3.update_layout(**BASE_LAYOUT,
                               title=dict(text="Findings by Category", font=dict(size=14, color="#e2e8f0")),
                               bargap=0.25)
            st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown("""
            <div style="height:200px;display:flex;align-items:center;justify-content:center;
                        color:#475569;font-size:13px;border:1px dashed rgba(255,255,255,0.07);
                        border-radius:12px">
                No findings to categorize
            </div>""", unsafe_allow_html=True)

    # ── Chart 4: Cyclomatic Complexity Gauge ─────────────────────────────────
    with col4:
        comp = code_res.get("complexity_score", {}) or {}
        cc = comp.get("cyclomatic", 0) or 0
        loc = comp.get("lines_of_code", 0) or 0

        gauge_color = "#10b981" if cc <= 5 else "#f59e0b" if cc <= 10 else "#ef4444"
        fig4 = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=cc,
            title={"text": "Cyclomatic Complexity", "font": {"size": 14, "color": "#e2e8f0"}},
            delta={"reference": 10, "increasing": {"color": "#ef4444"}, "decreasing": {"color": "#10b981"}},
            gauge={
                "axis": {"range": [0, 30], "tickcolor": "#475569",
                          "tickfont": {"color": "#64748b", "size": 10}},
                "bar": {"color": gauge_color},
                "bgcolor": "rgba(255,255,255,0.03)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 5],  "color": "rgba(16,185,129,0.1)"},
                    {"range": [5, 10], "color": "rgba(245,158,11,0.1)"},
                    {"range": [10, 30], "color": "rgba(239,68,68,0.1)"},
                ],
                "threshold": {"line": {"color": "#f59e0b", "width": 2}, "thickness": 0.75, "value": 10},
            },
            number={"font": {"size": 28, "color": gauge_color}},
        ))
        fig4.update_layout(**BASE_LAYOUT, height=250,
                           annotations=[dict(x=0.5, y=-0.12, showarrow=False,
                                             text=f"Lines of Code: <b>{loc}</b>",
                                             font=dict(size=12, color="#64748b"),
                                             xref="paper", yref="paper")])
        st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})


# ══════════════════════════════════════════════════════════════════════════════
# INLINE RESULTS RENDERER
# ══════════════════════════════════════════════════════════════════════════════
def render_results(res: dict, session_id: str) -> None:
    """Renders the full analysis report inline — risk banner, scores, charts, issue cards, download."""
    if not res:
        st.warning("No result data available.")
        return

    code_res = res.get("code_analysis")  or {}
    sec_res  = res.get("security_analysis") or {}
    rem_res  = res.get("remediation") or {}
    pr_res   = res.get("pr_summary") or {}
    language = res.get("language", "python")

    # ── Risk Banner ───────────────────────────────────────────────────────────
    risk = str(pr_res.get("overall_risk", "UNKNOWN")).upper() if pr_res else "UNKNOWN"
    approved = pr_res.get("approved", False) if pr_res else False

    RISK_MAP = {
        "CRITICAL": ("#7f1d1d", "#ef4444", "#fca5a5", "🚨"),
        "HIGH":     ("#7c2d12", "#f97316", "#fdba74", "🔴"),
        "MEDIUM":   ("#713f12", "#f59e0b", "#fde68a", "🟡"),
        "LOW":      ("#14532d", "#22c55e", "#86efac", "🟢"),
        "CLEAN":    ("#064e3b", "#10b981", "#6ee7b7", "✅"),
    }
    r_bg, r_border, r_text, r_icon = RISK_MAP.get(risk, ("#1e293b", "#475569", "#94a3b8", "❓"))
    total_findings = pr_res.get("total_findings", 0) if pr_res else 0
    composite = pr_res.get("composite_risk_score", "N/A") if pr_res else "N/A"
    approve_badge = (
        '<span style="background:#10b981;color:#fff;padding:4px 14px;border-radius:999px;font-size:12px;font-weight:700">✅ APPROVED</span>'
        if approved else
        '<span style="background:#ef4444;color:#fff;padding:4px 14px;border-radius:999px;font-size:12px;font-weight:700">❌ BLOCKED</span>'
    )

    st.markdown(f"""
    <div style="background:rgba(0,0,0,0.3);border:1px solid {r_border};border-radius:16px;
                padding:20px 24px;margin:16px 0;display:flex;
                align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
      <div>
        <div style="font-size:1.7rem;font-weight:900;color:{r_text}">
          {r_icon} Overall Risk: {risk}
        </div>
        <div style="color:#64748b;font-size:13px;margin-top:4px">
          Composite Score: <b style="color:{r_text}">{composite}</b>/100 &nbsp;|&nbsp;
          Total Findings: <b style="color:{r_text}">{total_findings}</b>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:12px">
        {approve_badge}
        <span style="font-size:12px;color:#475569">{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Score Cards ───────────────────────────────────────────────────────────
    q_score = code_res.get("quality_score", "—")
    q_grade = code_res.get("quality_grade", "—")
    s_score = sec_res.get("security_score", "—")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🔬 Quality Score", f"{q_score}/100" if isinstance(q_score, int) else q_score)
    with c2:
        st.metric("🏆 Quality Grade", q_grade)
    with c3:
        st.metric("🛡️ Security Score", f"{s_score}/100" if isinstance(s_score, int) else s_score)
    with c4:
        st.metric("⚡ Composite Risk", f"{composite}/100" if isinstance(composite, (int, float)) else composite)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── PR Summary ────────────────────────────────────────────────────────────
    if pr_res and pr_res.get("markdown_review"):
        with st.expander("📋 PR Review Summary", expanded=False):
            st.markdown(pr_res["markdown_review"])
            if pr_res.get("remediation_priority_list"):
                st.markdown("#### 🎯 Fix Priority")
                for i, item in enumerate(pr_res["remediation_priority_list"], 1):
                    st.markdown(f"{i}. {item}")

    # ── Charts ────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">📊 Analytics</div>', unsafe_allow_html=True)
    render_charts(code_res, sec_res)

    # ── Combined Issues List ─────────────────────────────────────────────────
    st.markdown('<div class="section-heading" style="margin-top:24px">🔍 All Findings & Remediations</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Security vulnerabilities and code quality issues with inline fix guidance</div>', unsafe_allow_html=True)

    # Build remediation lookup by finding_id
    rem_lookup: dict[str, dict] = {}
    if rem_res:
        for r in rem_res.get("remediations", []):
            fid = r.get("finding_id", "")
            if fid:
                rem_lookup[fid] = r

    SEV_ICON = {
        "CRITICAL": ("🔥", "critical"),
        "HIGH":     ("🔴", "high"),
        "MEDIUM":   ("⚠️", "medium"),
        "LOW":      ("🟢", "low"),
        "INFORMATIONAL": ("ℹ️", "info"),
    }

    # Security vulnerabilities
    vulns = sec_res.get("vulnerabilities", [])
    findings = code_res.get("findings", [])

    if not vulns and not findings:
        st.markdown("""
        <div class="glass-card glass-card-green" style="text-align:center;padding:32px">
          <div style="font-size:2.5rem">✅</div>
          <div style="font-size:1.1rem;font-weight:700;color:#10b981;margin-top:8px">Clean Code</div>
          <div style="color:#64748b;font-size:13px;margin-top:4px">No security vulnerabilities or quality issues detected</div>
        </div>""", unsafe_allow_html=True)
    else:
        # Security Vulnerabilities first
        if vulns:
            st.markdown("#### 🛡️ Security Vulnerabilities")
            for v in vulns:
                sev = str(v.get("severity", "medium")).upper()
                icon, cls = SEV_ICON.get(sev, ("⚪", "info"))
                vid = v.get("id", "")
                rem = rem_lookup.get(vid, {})
                cwe  = v.get("cwe_id", "")
                owasp = v.get("owasp_category", "")
                lines_txt = ""
                if v.get("line_start") and v.get("line_end"):
                    lines_txt = f"Lines {v['line_start']}–{v['line_end']}"
                elif v.get("line"):
                    lines_txt = f"Line {v['line']}"

                with st.expander(f"{icon} [{cwe or vid}] {v.get('title', 'Vulnerability')}  ·  {sev}", expanded=(sev in ("CRITICAL", "HIGH"))):
                    st.markdown(f"""
                    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
                      <span class="badge badge-{cls}">{sev}</span>
                      {"<span class='badge badge-info'>" + owasp.split(' - ')[-1] + "</span>" if owasp else ""}
                      {"<span class='badge badge-info'>📍 " + lines_txt + "</span>" if lines_txt else ""}
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"**Description:** {v.get('description', '')}")
                    if v.get("impact"):
                        st.markdown(f"**Impact:** {v['impact']}")
                    if v.get("evidence"):
                        st.code(v["evidence"], language=language)
                    if v.get("remediation"):
                        st.info(f"**Quick Fix:** {v['remediation']}")
                    if rem:
                        st.markdown("---")
                        st.markdown(f"**🔧 Remediation:** {rem.get('recommendation', '')}")
                        if rem.get("explanation"):
                            st.markdown(f"*{rem['explanation']}*")
                        if rem.get("corrected_code"):
                            st.markdown("**Corrected Code:**")
                            st.code(rem["corrected_code"], language=language)
                        if rem.get("references"):
                            st.caption("References: " + " · ".join(rem["references"]))

        # Code Quality Findings
        if findings:
            st.markdown("#### 📝 Code Quality Issues")
            for f in findings:
                sev = str(f.get("severity", "medium")).upper()
                icon, cls = SEV_ICON.get(sev, ("⚪", "info"))
                fid = f.get("id", "")
                rem = rem_lookup.get(fid, {})
                category = f.get("category", "").replace("_", " ").title()
                ls, le = f.get("line_start"), f.get("line_end")
                lines_txt = f"Lines {ls}–{le}" if (ls and le and ls != le) else (f"Line {ls}" if ls else "")

                with st.expander(f"{icon} {f.get('type', 'Finding').replace('_',' ').title()} — {category}  ·  {sev}"):
                    st.markdown(f"""
                    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
                      <span class="badge badge-{cls}">{sev}</span>
                      {"<span class='badge badge-info'>" + category + "</span>" if category else ""}
                      {"<span class='badge badge-info'>📍 " + lines_txt + "</span>" if lines_txt else ""}
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"**Description:** {f.get('description', '')}")
                    if f.get("suggestion"):
                        st.info(f"**Suggestion:** {f['suggestion']}")
                    if rem:
                        st.markdown("---")
                        st.markdown(f"**🔧 Fix:** {rem.get('recommendation', '')}")
                        if rem.get("corrected_code"):
                            st.code(rem["corrected_code"], language=language)

    # ── Download Button ───────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        label="⬇️ Download Full Report (JSON)",
        data=json.dumps(res, indent=2, default=str),
        file_name=f"code_review_{session_id[:8]}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
        key="download_report_btn",
    )


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="padding:12px 0 8px">
      <div style="font-size:1.1rem;font-weight:800;color:#e2e8f0">🛡️ AI Code Review</div>
      <div style="font-size:11px;color:#475569;margin-top:2px">Group 2 · Milestone 4</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # Language selector
    st.markdown('<div style="font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px">Language</div>', unsafe_allow_html=True)
    language_choice = st.selectbox(
        "Language",
        ["auto", "python", "java"],
        index=0,
        help="Auto-detect or manually specify the programming language.",
        label_visibility="collapsed",
    )

    st.markdown("---")

    # System Status
    st.markdown('<div style="font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">System Status</div>', unsafe_allow_html=True)
    api_ok = check_api()
    if api_ok:
        st.markdown('<span class="badge badge-ok">✅ API Online</span>', unsafe_allow_html=True)
        st.session_state.api_mode = "api"
    else:
        st.markdown('<span class="badge badge-medium">⚡ Local Mode</span>', unsafe_allow_html=True)
        st.caption("FastAPI not running. Start with:\n`uvicorn app.main:app --reload`")
        st.session_state.api_mode = "local"

    st.markdown("---")

    # Pipeline
    st.markdown('<div style="font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px">Agent Pipeline</div>', unsafe_allow_html=True)
    stages = [
        ("✅", "Code Analysis Agent",     "#10b981"),
        ("✅", "Security Vuln Agent",     "#10b981"),
        ("✅", "Remediation Agent",        "#10b981"),
        ("✅", "PR Summary Agent",         "#10b981"),
        ("✅", "Chat Assistant (RAG)",     "#10b981"),
    ]
    for icon, name, color in stages:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12px;color:{color}">'
            f'{icon} {name}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div style="font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px">Tech Stack</div>', unsafe_allow_html=True)
    st.caption("FastAPI · Streamlit · LangGraph\nCelery · Redis · Semgrep · Bandit\nGemini Flash · FAISS · Plotly")

    if st.session_state.last_session_id and st.session_state.api_mode == "api":
        st.markdown("---")
        st.markdown('<div style="font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px">Last Session</div>', unsafe_allow_html=True)
        short_id = st.session_state.last_session_id[:8]
        st.code(f"...{short_id}", language="text")


# ══════════════════════════════════════════════════════════════════════════════
# HERO HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
  <h1>🛡️ AI Code Review Agent</h1>
  <p>OWASP vulnerability detection · Code quality analysis · Intelligent remediation</p>
  <div class="hero-badges">
    <span class="badge badge-info">🐍 Python</span>
    <span class="badge badge-info">☕ Java</span>
    <span class="badge badge-critical">🔥 OWASP Top 10</span>
    <span class="badge badge-ok">✅ Semgrep + Bandit</span>
    <span class="badge badge-low">📊 4-Stage Pipeline</span>
  </div>
</div>
""", unsafe_allow_html=True)

mode = st.session_state.api_mode
if mode == "local":
    st.info("⚡ **Local Mode** — Start `uvicorn app.main:app --reload` for the full AI analysis pipeline.", icon="ℹ️")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_submit, tab_chat, tab_about = st.tabs([
    "🚀  Submit & Analyze",
    "💬  Chat Assistant",
    "ℹ️  About",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Submit & Analyze
# ══════════════════════════════════════════════════════════════════════════════
with tab_submit:
    col_input, col_results = st.columns([1, 1], gap="large")

    with col_input:
        st.markdown('<div class="section-heading">📋 Code Input</div>', unsafe_allow_html=True)

        input_mode = st.radio(
            "Input mode",
            ["✏️ Paste Code", "📁 Upload File"],
            horizontal=True,
            label_visibility="collapsed",
        )

        code_input = ""
        file_lang = language_choice

        if input_mode == "✏️ Paste Code":
            editor_lang = "python" if language_choice in ["python", "auto"] else "java"
            try:
                from streamlit_ace import st_ace
                code_input = st_ace(
                    placeholder="# Paste your Python or Java code here...\n\ndef example():\n    user_id = input('ID: ')\n    query = f'SELECT * FROM users WHERE id={user_id}'  # SQL injection!",
                    language=editor_lang, theme="monokai",
                    key="ace_editor", height=420, font_size=13,
                    show_gutter=True, show_print_margin=False,
                    wrap=False, auto_update=True,
                )
            except Exception:
                code_input = st.text_area(
                    "Source Code",
                    placeholder="# Paste your Python or Java code here...\n\ndef example():\n    user_id = input('ID: ')\n    query = f'SELECT * FROM users WHERE id={user_id}'  # SQL injection!",
                    height=420, key="code_textarea",
                    label_visibility="collapsed",
                )

        else:  # Upload File
            uploaded_file = st.file_uploader(
                "Drop your .py or .java file here",
                type=["py", "java"], key="file_uploader",
                label_visibility="collapsed",
            )
            if uploaded_file:
                try:
                    raw_bytes = uploaded_file.read()
                    code_input = raw_bytes.decode("utf-8")
                    file_lang = _detect_language(code_input, uploaded_file.name)
                    sz = len(raw_bytes) / 1024
                    st.success(f"✅ **{uploaded_file.name}** — {len(code_input.splitlines())} lines · {sz:.1f} KB · Detected: **{file_lang.upper()}**")
                    with st.expander("👁️ Preview", expanded=False):
                        preview = "\n".join(code_input.splitlines()[:50])
                        if len(code_input.splitlines()) > 50:
                            preview += f"\n\n# ... {len(code_input.splitlines()) - 50} more lines ..."
                        st.code(preview, language=file_lang if file_lang in ("python","java") else "text")
                except UnicodeDecodeError:
                    st.error("❌ File is not valid UTF-8.")
            else:
                st.markdown("""
                <div style="text-align:center;padding:60px 20px;color:#475569">
                  <div style="font-size:3rem">📁</div>
                  <p style="margin:12px 0 4px;font-size:14px">Drop a <b>.py</b> or <b>.java</b> file</p>
                  <p style="font-size:12px;color:#334155">Max 5 MB · Max 10,000 lines</p>
                </div>""", unsafe_allow_html=True)

        # Live validation feedback
        actual_lang = file_lang if input_mode == "📁 Upload File" else \
                      (_detect_language(code_input) if language_choice == "auto" else language_choice)
        is_valid_code = False

        if code_input and code_input.strip():
            lines_count = len(code_input.splitlines())
            chars_count = len(code_input)

            m1, m2, m3 = st.columns(3)
            m1.metric("Lines", lines_count)
            m2.metric("Characters", chars_count)
            m3.metric("Language", actual_lang.upper())

            live_val = _local_validate(code_input, actual_lang)
            is_valid_code = live_val.get("valid", False)

            if live_val["valid"]:
                st.markdown("""
                <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);
                            border-radius:8px;padding:10px 14px;margin:8px 0;display:flex;align-items:center;gap:8px">
                  <span>✅</span>
                  <span style="color:#10b981;font-weight:600;font-size:13px">Syntax Valid</span>
                </div>""", unsafe_allow_html=True)
            else:
                error_count = len(live_val.get("errors", []))
                st.markdown(f"""
                <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.3);
                            border-radius:8px;padding:10px 14px;margin:8px 0">
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                    <span>❌</span>
                    <span style="color:#ef4444;font-weight:600;font-size:13px">{error_count} Syntax Error{'s' if error_count > 1 else ''}</span>
                  </div>""", unsafe_allow_html=True)
                for err in live_val.get("errors", []):
                    msg = err.get("message", "")
                    line_no = err.get("line")
                    loc_txt = f"Line {line_no} → " if line_no else ""
                    st.markdown(f"""
                  <div style="background:rgba(0,0,0,0.3);border-left:3px solid #ef4444;
                              padding:5px 12px;margin:3px 0;border-radius:0 6px 6px 0;font-family:monospace;font-size:12px">
                    <span style="color:#fca5a5">{loc_txt}{msg}</span>
                  </div>""", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

        # Submit button
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_btn = st.button(
            "🚀 Run Full AI Analysis",
            key="analyze_btn",
            type="primary",
            disabled=not is_valid_code,
            use_container_width=True,
        )

        if analyze_btn:
            if not code_input or not code_input.strip():
                st.warning("⚠️ Please enter some code first.")
            else:
                with st.spinner("Submitting to analysis pipeline..."):
                    lang_to_use = file_lang if input_mode == "📁 Upload File" else language_choice
                    if input_mode == "📁 Upload File" and uploaded_file:
                        resp = api_submit_file(raw_bytes, uploaded_file.name, lang_to_use)
                    else:
                        resp = api_submit_paste(code_input, lang_to_use)

                if isinstance(resp.get("detail"), dict):
                    st.error("❌ Submission failed — validation errors:")
                    if "errors" in resp["detail"]:
                        for err in resp["detail"]["errors"]:
                            st.code(err.get("message", ""), language="text")
                    elif "reason" in resp["detail"]:
                        st.code(f"{resp['detail'].get('message', '')}\nReason: {resp['detail']['reason']}", language="text")
                elif resp.get("error"):
                    st.error(f"❌ {resp['error']}")
                else:
                    sid = resp.get("session_id")
                    st.session_state.last_session_id = sid
                    st.session_state.last_result = None
                    st.session_state.polling = True
                    st.rerun()

        # Polling loop
        if st.session_state.polling and st.session_state.last_session_id:
            sid = st.session_state.last_session_id
            if mode == "api":
                with st.spinner("⏳ Analysis running — polling for results..."):
                    progress = st.progress(0, text="Waiting for pipeline...")
                    finished = False
                    for pct in range(0, 95, 5):
                        time.sleep(3)
                        status_data = api_status(sid)
                        current_status = status_data.get("status", "queued")
                        stage = status_data.get("current_stage", "")
                        progress.progress(pct, text=f"Stage: {stage or current_status}")
                        if current_status == "completed":
                            finished = True
                            break
                        if current_status == "failed":
                            st.error(f"❌ Analysis failed: {status_data.get('error_message', 'Unknown error')}")
                            st.session_state.polling = False
                            break
                    progress.empty()

                if not finished and st.session_state.polling:
                    st.warning("⚠️ Analysis is taking longer than expected. Please manually refresh the result in a few moments.")
                    st.session_state.polling = False
                    st.rerun()
                elif finished:
                    result_data = api_fetch_result(sid)
                    if result_data.get("error") and not result_data.get("code_analysis"):
                        st.warning(f"⚠️ Analysis may still be processing: {result_data.get('error')}")
                    else:
                        st.session_state.last_result = result_data
                        st.session_state.polling = False
                        st.rerun()
            else:
                st.session_state.polling = False

    # ── Results panel ────────────────────────────────────────────────────────
    with col_results:
        if st.session_state.last_result:
            render_results(st.session_state.last_result, st.session_state.last_session_id or "unknown")
        elif st.session_state.last_session_id and not st.session_state.polling:
            st.markdown("""
            <div class="glass-card" style="text-align:center;padding:40px 24px">
              <div style="font-size:2.5rem;margin-bottom:12px">🔍</div>
              <div style="color:#94a3b8;font-size:14px">Analysis in progress or result not yet available.</div>
              <div style="color:#475569;font-size:12px;margin-top:8px">Refresh manually or re-submit.</div>
            </div>""", unsafe_allow_html=True)

            if mode == "api":
                if st.button("🔄 Refresh Result", key="manual_refresh"):
                    sid = st.session_state.last_session_id
                    result_data = api_fetch_result(sid)
                    if not result_data.get("error") or result_data.get("code_analysis"):
                        st.session_state.last_result = result_data
                        st.rerun()
                    else:
                        st.warning("Still processing — please wait a moment and try again.")
        else:
            st.markdown("""
            <div style="height:100%;display:flex;align-items:center;justify-content:center;
                        padding:60px 24px;text-align:center">
              <div>
                <div style="font-size:4rem;margin-bottom:16px;opacity:0.3">🛡️</div>
                <div style="color:#334155;font-size:1rem;font-weight:600">Results will appear here</div>
                <div style="color:#1e293b;font-size:13px;margin-top:6px">
                  Submit code on the left to run the full<br>multi-agent security & quality analysis
                </div>
              </div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Chat Assistant
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown('<div class="section-heading">💬 Conversational Code Assistant</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Ask follow-up questions about your last analysis result. Powered by RAG + Gemini.</div>', unsafe_allow_html=True)

    if mode == "local":
        st.warning("⚡ Chat requires the FastAPI backend. Start with: `uvicorn app.main:app --reload`")
    elif not st.session_state.last_session_id:
        st.info("💡 Submit and analyze code first, then return here to chat about the findings.")
    else:
        sid = st.session_state.last_session_id
        st.markdown(f'<div style="font-size:12px;color:#475569;margin-bottom:12px">Session: <code>{sid[:16]}...</code></div>', unsafe_allow_html=True)

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_q := st.chat_input("Ask about vulnerabilities, fixes, or secure coding guidelines..."):
            st.session_state.chat_history.append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.markdown(user_q)
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    res = api_chat(sid, user_q)
                    if "error" in res:
                        answer = f"❌ Error: {res['error']}"
                    else:
                        answer = res.get("response", "No answer generated.")
                    st.markdown(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — About
# ══════════════════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown('<div class="section-heading">About This Project</div>', unsafe_allow_html=True)

    col_ab1, col_ab2 = st.columns(2)

    with col_ab1:
        st.markdown("""
        <div class="glass-card glass-card-blue">
          <h4 style="color:#a5b4fc;margin-top:0">🎯 What This Does</h4>
          <p style="color:#94a3b8;font-size:14px;line-height:1.8">
            An AI-powered platform that automatically analyzes Python and Java source code for:
          </p>
          <ul style="color:#94a3b8;line-height:2.2;font-size:14px">
            <li>🛡️ OWASP Top-10 security vulnerabilities (CWE-tagged)</li>
            <li>🔍 Code smells &amp; design anti-patterns</li>
            <li>📊 Cyclomatic complexity &amp; maintainability metrics</li>
            <li>🔧 Corrected code &amp; RAG-grounded remediation</li>
            <li>💬 Conversational follow-up Q&amp;A</li>
          </ul>
        </div>

        <div class="glass-card glass-card-purple" style="margin-top:12px">
          <h4 style="color:#c4b5fd;margin-top:0">🔁 4-Stage Pipeline</h4>
          <div style="color:#94a3b8;font-size:13px;line-height:2.4">
            <div><b style="color:#818cf8">Stage 1 (Parallel A)</b> Code Analysis Agent → Pylint + Radon + Gemini</div>
            <div><b style="color:#818cf8">Stage 1 (Parallel B)</b> Security Agent → Bandit/Semgrep + Gemini</div>
            <div><b style="color:#818cf8">Stage 2</b> Sync Findings → merge parallel outputs</div>
            <div><b style="color:#818cf8">Stage 3</b> Remediation Agent → RAG-grounded code fixes</div>
            <div><b style="color:#818cf8">Stage 4</b> PR Summary Agent → risk rating + approve/reject</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_ab2:
        st.markdown("""
        <div class="glass-card glass-card-green">
          <h4 style="color:#6ee7b7;margin-top:0">🛠️ Tech Stack</h4>
          <table style="width:100%;border-collapse:collapse;color:#94a3b8;font-size:13px">
            <tr><td style="padding:7px 0;color:#475569;width:130px">LLM</td><td>Google Gemini Flash / Pro</td></tr>
            <tr><td style="padding:7px 0;color:#475569">Security Lint</td><td>Semgrep (p/java) + Bandit</td></tr>
            <tr><td style="padding:7px 0;color:#475569">Quality Lint</td><td>Pylint + Radon</td></tr>
            <tr><td style="padding:7px 0;color:#475569">RAG</td><td>LlamaIndex + FAISS + BM25</td></tr>
            <tr><td style="padding:7px 0;color:#475569">Agents</td><td>LangGraph StateGraph (fan-out)</td></tr>
            <tr><td style="padding:7px 0;color:#475569">Backend</td><td>FastAPI + Celery + Redis</td></tr>
            <tr><td style="padding:7px 0;color:#475569">Frontend</td><td>Streamlit + Plotly</td></tr>
            <tr><td style="padding:7px 0;color:#475569">Tracing</td><td>LangSmith + Logfire</td></tr>
            <tr><td style="padding:7px 0;color:#475569">Testing</td><td>pytest · 49 tests · 61% coverage</td></tr>
          </table>
        </div>

        <div class="glass-card" style="margin-top:12px">
          <h4 style="color:#a5b4fc;margin-top:0">📅 Milestone Status</h4>
          <div style="font-size:13px;line-height:2.4">
            <div style="color:#10b981">✅ <b>M1</b> Foundation · Code Submission · RAG Knowledge Base</div>
            <div style="color:#10b981">✅ <b>M2</b> Multi-Agent Pipeline · Parallel LangGraph</div>
            <div style="color:#10b981">✅ <b>M3</b> Guardrails · Semgrep · Chat Interface</div>
            <div style="color:#f59e0b">🔄 <b>M4</b> Report Export · Charts · UI Redesign</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style="text-align:center;padding:20px;color:#334155;font-size:13px">
      <b style="color:#6366f1">Group 2</b> · AI Code Review &amp; Security Analysis Agent ·
      <a href="https://github.com/shubham0915/AI-Code-Review-Security-Analysis-Agent-Group2"
         style="color:#6366f1;text-decoration:none">GitHub Repository</a><br>
      <span style="color:#1e293b;font-size:12px">Milestone 4 · 100% Open-Source · Runs on Apple M4</span>
    </div>
    """, unsafe_allow_html=True)