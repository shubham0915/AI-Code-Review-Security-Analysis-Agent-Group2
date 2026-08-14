"""
tests/unit/test_agents.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests for all four LangGraph agents:
  1. Code Analysis Agent
  2. Security Vulnerability Agent
  3. Remediation Agent
  4. PR Summary Agent

All tests use mocked LLM calls — no live Ollama or Gemini required.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage

from app.models import (
    CodeAnalysisResult,
    SecurityAnalysisResult,
    RemediationResult,
    PRSummaryResult,
    OverallRiskRating,
    Severity,
)
from app.agents.state import AgentState
from app.agents.nodes.code_analysis import run_code_analysis
from app.agents.nodes.security_vuln import run_security_vuln
from app.agents.nodes.remediation import run_remediation, _collect_findings, _build_rag_query
from app.agents.nodes.pr_summary import run_pr_summary, _compute_fallback_scores


# ─── Shared Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_state() -> AgentState:
    """Minimal valid AgentState for testing agents in isolation."""
    return {
        "session_id": "test-123",
        "code": "def foo(): pass",
        "language": "python",
        "linter_output": {"pylint": []},
        "code_analysis_result": None,
        "security_analysis_result": None,
        "remediation_result": None,
        "pr_summary_result": None,
    }


@pytest.fixture
def state_with_findings() -> AgentState:
    """AgentState pre-populated with code analysis and security results for downstream tests."""
    ca_result = CodeAnalysisResult(
        findings=[],
        quality_score=70,
        quality_grade="C",
        summary="Two code smells detected.",
    )
    sec_result = SecurityAnalysisResult(
        vulnerabilities=[],
        security_score=65,
        high_count=1,
        summary="One high-severity SQL injection found.",
    )
    return {
        "session_id": "test-456",
        "code": "def get_user(uid): return db.execute(f'SELECT * FROM users WHERE id={uid}')",
        "language": "python",
        "linter_output": {"bandit": {"results": []}},
        "code_analysis_result": ca_result,
        "security_analysis_result": sec_result,
        "remediation_result": None,
        "pr_summary_result": None,
    }


# ─── Agent 1: Code Analysis ───────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.agents.nodes.code_analysis.get_llm")
async def test_run_code_analysis(mock_get_llm, sample_state):
    """Code Analysis Agent should return a valid CodeAnalysisResult."""
    with patch(
        "langchain_core.runnables.RunnableSequence.ainvoke", new_callable=AsyncMock
    ) as mock_chain_ainvoke:
        mock_chain_ainvoke.return_value = CodeAnalysisResult(
            summary="Looks good", quality_score=95, quality_grade="A"
        )
        result = await run_code_analysis(sample_state)

        assert "code_analysis_result" in result
        assert isinstance(result["code_analysis_result"], CodeAnalysisResult)
        assert result["code_analysis_result"].summary == "Looks good"
        assert result["code_analysis_result"].quality_score == 95


@pytest.mark.asyncio
@patch("app.agents.nodes.code_analysis.get_llm")
async def test_run_code_analysis_json_fallback(mock_get_llm, sample_state):
    """Code Analysis Agent should use error fallback when LLM returns invalid JSON twice."""
    with patch(
        "langchain_core.runnables.RunnableSequence.ainvoke", new_callable=AsyncMock
    ) as mock_chain_ainvoke:
        # Simulate bad JSON on both attempts
        mock_chain_ainvoke.return_value = AIMessage(content="NOT VALID JSON AT ALL !!!")
        result = await run_code_analysis(sample_state)

        assert "code_analysis_result" in result
        ca = result["code_analysis_result"]
        assert isinstance(ca, CodeAnalysisResult)
        # Fallback always returns score=0 and grade=F
        assert ca.quality_score == 0
        assert ca.quality_grade == "F"
        assert "[PARSE ERROR]" in ca.summary


# ─── Agent 2: Security Vulnerability ─────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.agents.nodes.security_vuln.get_llm")
@patch("app.agents.nodes.security_vuln.query_index")
async def test_run_security_vuln(mock_query_index, mock_get_llm, sample_state):
    """Security Vulnerability Agent should return a valid SecurityAnalysisResult."""
    mock_query_index.return_value = ""  # Disable RAG for simplicity

    with patch(
        "langchain_core.runnables.RunnableSequence.ainvoke", new_callable=AsyncMock
    ) as mock_chain_ainvoke:
        # Return valid JSON as AIMessage — this is what the real LLM returns
        mock_chain_ainvoke.return_value = AIMessage(
            content=json.dumps({
                "agent": "SecurityVulnerabilityAgent",
                "vulnerabilities": [],
                "security_score": 100,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "summary": "No vulnerabilities",
            })
        )
        result = await run_security_vuln(sample_state)

        assert "security_analysis_result" in result
        assert isinstance(result["security_analysis_result"], SecurityAnalysisResult)
        assert result["security_analysis_result"].security_score == 100


# ─── Agent 3: Remediation ─────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.agents.nodes.remediation.get_llm")
@patch("app.agents.nodes.remediation.query_index")
async def test_run_remediation_with_findings(mock_query_index, mock_get_llm, state_with_findings):
    """Remediation Agent should return a valid RemediationResult when findings exist."""
    mock_query_index.return_value = ""  # Disable RAG

    # Inject a real code smell so _collect_findings returns non-empty list
    from app.models import CodeSmell
    state_with_findings["code_analysis_result"].findings = [
        CodeSmell(
            id="ca-001",
            type="code_smell",
            severity=Severity.high,
            description="SQL injection via f-string formatting",
            suggestion="Use parameterized queries.",
        )
    ]

    with patch(
        "langchain_core.runnables.RunnableSequence.ainvoke", new_callable=AsyncMock
    ) as mock_chain_ainvoke:
        mock_chain_ainvoke.return_value = AIMessage(
            content=json.dumps({
                "agent": "RemediationAgent",
                "remediations": [],
                "summary": "Use parameterized queries to fix SQL injection.",
            })
        )
        result = await run_remediation(state_with_findings)

        assert "remediation_result" in result
        assert isinstance(result["remediation_result"], RemediationResult)
        assert "parameterized" in result["remediation_result"].summary


@pytest.mark.asyncio
@patch("app.agents.nodes.remediation.get_llm")
@patch("app.agents.nodes.remediation.query_index")
async def test_run_remediation_no_findings(mock_query_index, mock_get_llm, sample_state):
    """Remediation Agent should return clean result immediately when there are no findings."""
    mock_query_index.return_value = ""
    # No LLM call should happen — agent returns early
    result = await run_remediation(sample_state)

    assert "remediation_result" in result
    rem = result["remediation_result"]
    assert isinstance(rem, RemediationResult)
    assert rem.remediations == []
    assert "No findings" in rem.summary


def test_collect_findings_code_smells(state_with_findings):
    """_collect_findings should correctly extract code analysis findings."""
    # Inject a real finding into the fixture
    from app.models import CodeSmell
    ca = state_with_findings["code_analysis_result"]
    ca.findings = [
        CodeSmell(
            id="ca-001",
            type="code_smell",
            severity=Severity.medium,
            description="Missing docstring",
        )
    ]
    findings = _collect_findings(state_with_findings)
    assert len(findings) >= 1
    assert any(f["id"] == "ca-001" for f in findings)


def test_build_rag_query_security_priority():
    """_build_rag_query should prioritize security findings."""
    findings = [
        {"type": "security_vulnerability", "description": "SQL Injection"},
        {"type": "code_smell", "description": "Missing docstring"},
    ]
    query = _build_rag_query(findings)
    assert "SQL Injection" in query
    assert "remediation" in query.lower()


# ─── Agent 4: PR Summary ──────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.agents.nodes.pr_summary.get_fast_llm")
async def test_run_pr_summary(mock_get_llm, state_with_findings):
    """PR Summary Agent should return a valid PRSummaryResult."""
    with patch(
        "langchain_core.runnables.RunnableSequence.ainvoke", new_callable=AsyncMock
    ) as mock_chain_ainvoke:
        mock_chain_ainvoke.return_value = AIMessage(
            content=json.dumps({
                "agent": "PRSummaryAgent",
                "overall_risk": "HIGH",
                "security_score": 65,
                "quality_score": 70,
                "composite_risk_score": 33,
                "total_findings": 1,
                "markdown_review": "## 🤖 AI Code Review Report\n**Risk:** HIGH",
                "remediation_priority_list": ["Fix SQL injection first"],
                "approved": False,
            })
        )
        result = await run_pr_summary(state_with_findings)

        assert "pr_summary_result" in result
        pr = result["pr_summary_result"]
        assert isinstance(pr, PRSummaryResult)
        assert pr.overall_risk == OverallRiskRating.high
        assert pr.approved is False
        assert pr.security_score == 65


@pytest.mark.asyncio
@patch("app.agents.nodes.pr_summary.get_fast_llm")
async def test_run_pr_summary_fallback(mock_get_llm, state_with_findings):
    """PR Summary Agent should use deterministic fallback when LLM fails twice."""
    with patch(
        "langchain_core.runnables.RunnableSequence.ainvoke", new_callable=AsyncMock
    ) as mock_chain_ainvoke:
        mock_chain_ainvoke.return_value = AIMessage(content="THIS IS NOT JSON")
        result = await run_pr_summary(state_with_findings)

        assert "pr_summary_result" in result
        pr = result["pr_summary_result"]
        assert isinstance(pr, PRSummaryResult)
        # Fallback should compute from actual agent scores in state
        assert pr.security_score == 65  # From state_with_findings fixture
        assert pr.quality_score == 70


def test_compute_fallback_scores_clean_state(sample_state):
    """_compute_fallback_scores should return CLEAN for empty findings."""
    scores = _compute_fallback_scores(sample_state)
    assert scores["overall_risk"] == "CLEAN"
    assert scores["total_findings"] == 0
    assert scores["approved"] is True


def test_compute_fallback_scores_high_risk(state_with_findings):
    """_compute_fallback_scores should return HIGH for state with high severity findings."""
    scores = _compute_fallback_scores(state_with_findings)
    # high_count=1 in the fixture's security result
    assert scores["overall_risk"] == "HIGH"
    assert scores["approved"] is False
