"""
About this file: graph.py
Structure: StateGraph build script linking Code Analysis, Security, Remediation, and PR Summary nodes with branching conditions.
Methods used: code_analysis_node, security_node, remediation_node, pr_summary_node, build_graph.
"""

from langgraph.graph import StateGraph, END
from loguru import logger

from app.agents.state import AgentState
from app.agents.nodes import (
    run_code_analysis,
    run_security_vuln,
    run_remediation,
    run_pr_summary,
)
from app.linters import run_python_linters, run_java_linters


# ─── Stage 1: Linters ─────────────────────────────────────────────────────────

async def linters_node(state: AgentState) -> dict:
    """
    Runs static analysis tools (Bandit, Pylint, Radon for Python;
    regex heuristics for Java) before the LLM agents.
    """
    language = state.get("language", "python").lower()
    code = state.get("code", "")
    logger.info(f"[STAGE 1/5] Linters — language={language}, session={state.get('session_id')}")
    try:
        if language == "python":
            return {"linter_output": await run_python_linters(code)}
        elif language == "java":
            return {"linter_output": await run_java_linters(code)}
        return {"linter_output": {"error": f"Unsupported language: {language}"}}
    except Exception as e:
        logger.error(f"Linters failed: {e}")
        return {"linter_output": {"error": str(e)}}


# ─── Thin wrappers: inject stage logging without polluting node files ──────────

async def code_analysis_node(state: AgentState) -> dict:
    """
    Executes the Code Analysis agent node to detect code smells, anti-patterns, and linting rule violations.
    """
    logger.info(f"[STAGE 2/5] Code Analysis — session={state.get('session_id')}")
    result = await run_code_analysis(state)

    # Inject real Radon metrics (cyclomatic complexity, LOC) into the result
    # so the UI never shows placeholder zeros.
    ca = result.get("code_analysis_result")
    linter_out = state.get("linter_output", {})
    if ca and "radon" in linter_out and isinstance(linter_out["radon"], dict):
        radon = linter_out["radon"]
        max_cc = max(
            (b.get("complexity", 0)
             for blocks in radon.get("cc", {}).values() if isinstance(blocks, list)
             for b in blocks if isinstance(b, dict)),
            default=0,
        )
        ca.complexity_score.cyclomatic = max_cc
        ca.complexity_score.lines_of_code = sum(
            s.get("loc", 0)
            for s in radon.get("raw", {}).values() if isinstance(s, dict)
        )
    return result


async def security_node(state: AgentState) -> dict:
    """
    Executes the Security agent node to detect OWASP vulnerabilities, injection risks, and bad cryptography.
    """
    logger.info(f"[STAGE 3/5] Security — session={state.get('session_id')}")
    return await run_security_vuln(state)


async def remediation_node(state: AgentState) -> dict:
    """
    Executes the Remediation agent node to formulate concrete code fixes and remediation advice based on findings.
    """
    logger.info(f"[STAGE 4/5] Remediation — session={state.get('session_id')}")
    return await run_remediation(state)


async def pr_summary_node(state: AgentState) -> dict:
    """
    Executes the PR Summary agent node to synthesize all findings into a structured markdown pull-request review comment.
    """
    logger.info(f"[STAGE 5/5] PR Summary — session={state.get('session_id')}")
    return await run_pr_summary(state)


# ─── Conditional routing (MARATHON pattern) ────────────────────────────────────

def route_after_security(state: AgentState) -> str:
    """
    If both agents found zero findings → skip Remediation (save one LLM call).
    If any finding exists → run Remediation so developers get concrete fixes.
    """
    ca = state.get("code_analysis_result")
    sa = state.get("security_analysis_result")
    has_findings = bool(
        (ca and ca.findings) or
        (sa and sa.vulnerabilities)
    )
    target = "remediation" if has_findings else "pr_summary"
    logger.info(f"[ROUTER] has_findings={has_findings} → routing to '{target}'")
    return target


# ─── Graph assembly ────────────────────────────────────────────────────────────

def build_analysis_graph():
    """
    Builds and compiles the LangGraph pipeline.

    Pipeline (sequential with one conditional shortcut):
      linters → code_analysis → security_vuln
                                     ├── (findings)  → remediation → pr_summary → END
                                     └── (clean)                  → pr_summary → END
    """
    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("run_linters",    linters_node)
    builder.add_node("code_analysis",  code_analysis_node)
    builder.add_node("security_vuln",  security_node)
    builder.add_node("remediation",    remediation_node)
    builder.add_node("pr_summary",     pr_summary_node)

    # Fixed edges
    builder.set_entry_point("run_linters")
    builder.add_edge("run_linters",   "code_analysis")
    builder.add_edge("code_analysis", "security_vuln")

    # Conditional edge: skip remediation for clean code
    builder.add_conditional_edges(
        "security_vuln",
        route_after_security,
        {
            "remediation": "remediation",
            "pr_summary":  "pr_summary",
        },
    )

    builder.add_edge("remediation", "pr_summary")
    builder.add_edge("pr_summary",  END)

    return builder.compile()


analysis_graph = build_analysis_graph()