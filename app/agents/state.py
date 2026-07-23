"""
app/agents/state.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PURPOSE: Defines the shared "memory" that flows between all LangGraph nodes.

         Think of AgentState as a baton in a relay race.
         Each agent (node) in the LangGraph pipeline receives this state,
         reads what it needs, adds its own results, and passes it forward
         to the next agent.

WHY A SEPARATE FILE?
  AgentState is defined here (not in graph.py) to avoid a circular import:
    graph.py imports code_analysis.py
    code_analysis.py needs AgentState
    → If AgentState were in graph.py, we'd have a circular import loop.
    → Keeping it in its own file breaks the cycle cleanly.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from typing import TypedDict, Optional, Dict, Any
from app.models import CodeAnalysisResult, SecurityAnalysisResult


class AgentState(TypedDict):
    """
    The shared state dictionary passed between every node in the LangGraph pipeline.

    Fields are populated incrementally as the pipeline progresses:
      - session_id, code, language: Set at the very beginning (by the Celery task)
      - linter_output: Filled in by the run_linters node (Stage 1)
      - code_analysis_result: Filled in by the Code Analysis Agent (Stage 2a)
      - security_analysis_result: Filled in by the Security Agent (Stage 2b)
    """
    session_id: str             # Unique ID for this analysis job (UUID)
    code: str                   # The raw source code submitted by the user
    language: str               # "python" or "java"
    linter_output: Dict[str, Any]   # Raw JSON output from Bandit/Pylint/Radon/PMD

    # These start as None and get populated as each agent finishes
    code_analysis_result: Optional[CodeAnalysisResult]
    security_analysis_result: Optional[SecurityAnalysisResult]
