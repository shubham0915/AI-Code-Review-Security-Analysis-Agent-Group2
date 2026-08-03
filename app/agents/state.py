"""
About this file: state.py
Structure: Data structures encapsulating code inputs, linter findings, node results, and routing flags across agents.
Methods used: AgentState, ChatState.
"""

from typing import TypedDict, Optional, Dict, Any
from app.models import (
    CodeAnalysisResult,
    SecurityAnalysisResult,
    RemediationResult,
    PRSummaryResult,
)


class AgentState(TypedDict):
    """
    The shared state dictionary passed between every node in the LangGraph pipeline.

    Fields are populated incrementally as the pipeline progresses:
      - session_id, code, language: Set at the very beginning (by the Celery task)
      - linter_output: Filled in by the run_linters node (Stage 1)
      - code_analysis_result: Filled in by the Code Analysis Agent (Stage 2)
      - security_analysis_result: Filled in by the Security Agent (Stage 3)
      - remediation_result: Filled in by the Remediation Agent (Stage 4)
      - pr_summary_result: Filled in by the PR Summary Agent (Stage 5)
    """
    session_id: str                 # Unique ID for this analysis job (UUID)
    code: str                       # The raw source code submitted by the user
    language: str                   # "python" or "java"
    linter_output: Dict[str, Any]   # Raw JSON output from Bandit/Pylint/Radon/PMD

    # These start as None and get populated as each agent finishes
    code_analysis_result: Optional[CodeAnalysisResult]
    security_analysis_result: Optional[SecurityAnalysisResult]
    remediation_result: Optional[RemediationResult]       # Stage 4 — Remediation Agent
    pr_summary_result: Optional[PRSummaryResult]          # Stage 5 — PR Summary Agent
