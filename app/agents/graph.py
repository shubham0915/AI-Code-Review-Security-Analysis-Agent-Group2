"""
About this file: graph.py
Structure: StateGraph build script linking Code Analysis, Security, Remediation, and PR Summary nodes
           using parallel fan-out architecture. Linters now run inside each agent node directly.
Methods used: code_analysis_node, security_node, sync_findings_node, remediation_node,
              pr_summary_node, build_analysis_graph.
"""

from langgraph.graph import StateGraph, START, END
from loguru import logger

from app.agents.state import AgentState
from app.agents.nodes import (
    run_code_analysis,
    run_security_vuln,
    run_remediation,
    run_pr_summary,
)


# ─── Stage 1+2 (merged): Parallel Discovery — each agent runs its own linters ─

async def code_analysis_node(state: AgentState) -> dict:
    """
    Executes the Code Analysis agent node concurrently.
    Internally runs Pylint + Radon quality linters before calling the LLM.
    """
    logger.info(f"[STAGE 1/4 - PARALLEL BRANCH A] Code Analysis — session={state.get('session_id')}")
    return await run_code_analysis(state)


async def security_node(state: AgentState) -> dict:
    """
    Executes the Security agent node concurrently.
    Internally runs Bandit (Python) or Semgrep (Java) before calling the LLM.
    """
    logger.info(f"[STAGE 1/4 - PARALLEL BRANCH B] Security — session={state.get('session_id')}")
    return await run_security_vuln(state)


# ─── Stage 2: Convergence Synchronization ─────────────────────────────────────

async def sync_findings_node(state: AgentState) -> dict:
    """
    Convergence synchronization point after parallel execution of Code Analysis and Security agents.
    Ensures state updates from both parallel branches are consolidated before conditional routing.
    """
    logger.info(f"[STAGE 2/4 - CONVERGENCE] Synchronized scan findings — session={state.get('session_id')}")
    return {}


# ─── Stage 3 & 4: Remediation & Synthesis ─────────────────────────────────────

async def remediation_node(state: AgentState) -> dict:
    """
    Executes the Remediation agent node to formulate concrete code fixes and remediation advice.
    """
    logger.info(f"[STAGE 3/4] Remediation — session={state.get('session_id')}")
    return await run_remediation(state)


async def pr_summary_node(state: AgentState) -> dict:
    """
    Executes the PR Summary agent node to synthesize all findings into a structured markdown
    pull-request review summary.
    """
    logger.info(f"[STAGE 4/4] PR Summary — session={state.get('session_id')}")
    return await run_pr_summary(state)


# ─── Conditional routing (skip Remediation when code is clean) ────────────────

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
    Builds and compiles the LangGraph pipeline with parallel execution.

    Pipeline (parallel fan-out / fan-in with conditional shortcut):
                  ┌─➔ code_analysis (Pylint+Radon inside) ─┐
      [START]     ┼                                          ┼➔ sync_findings ├── (findings) → remediation → pr_summary → END
                  └─➔ security_vuln (Bandit/Semgrep inside) ┘               └── (clean)    ──────────────→ pr_summary → END
    """
    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("code_analysis", code_analysis_node)
    builder.add_node("security_vuln",  security_node)
    builder.add_node("sync_findings",  sync_findings_node)
    builder.add_node("remediation",    remediation_node)
    builder.add_node("pr_summary",     pr_summary_node)

    # Parallel Fan-Out directly from START (no separate linters node)
    builder.add_edge(START,           "code_analysis")
    builder.add_edge(START,           "security_vuln")

    # Parallel Fan-In Convergence Edges
    builder.add_edge("code_analysis", "sync_findings")
    builder.add_edge("security_vuln", "sync_findings")

    # Conditional edge: skip remediation for clean code
    builder.add_conditional_edges(
        "sync_findings",
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