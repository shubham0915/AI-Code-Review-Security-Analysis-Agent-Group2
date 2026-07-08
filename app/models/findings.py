"""
app/models/findings.py — Pydantic models for agent analysis findings.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    informational = "informational"


class OwaspCategory(str, Enum):
    A01 = "A01:2021 - Broken Access Control"
    A02 = "A02:2021 - Cryptographic Failures"
    A03 = "A03:2021 - Injection"
    A04 = "A04:2021 - Insecure Design"
    A05 = "A05:2021 - Security Misconfiguration"
    A06 = "A06:2021 - Vulnerable and Outdated Components"
    A07 = "A07:2021 - Identification and Authentication Failures"
    A08 = "A08:2021 - Software and Data Integrity Failures"
    A09 = "A09:2021 - Security Logging and Monitoring Failures"
    A10 = "A10:2021 - Server-Side Request Forgery"


class CodeSmell(BaseModel):
    """A single code quality finding from the Code Analysis Agent."""
    id: str
    type: str = Field(..., description="Finding type, e.g. code_smell, anti_pattern, complexity")
    category: str = Field(..., description="Specific category, e.g. god_class, long_method")
    severity: Severity
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    description: str
    snippet: Optional[str] = None
    suggestion: Optional[str] = None


class ComplexityScore(BaseModel):
    cyclomatic: int = 0
    cognitive: int = 0
    lines_of_code: int = 0
    duplication_pct: float = 0.0
    maintainability_index: Optional[float] = None


class CodeAnalysisResult(BaseModel):
    """Output from the Code Analysis Agent."""
    agent: str = "CodeAnalysisAgent"
    findings: list[CodeSmell] = []
    complexity_score: ComplexityScore = ComplexityScore()
    quality_grade: str = "N/A"   # A-F
    quality_score: int = 0       # 0-100
    summary: str = ""


class SecurityVulnerability(BaseModel):
    """A single security vulnerability finding."""
    id: str
    owasp_category: Optional[OwaspCategory] = None
    cwe_id: Optional[str] = None
    severity: Severity
    cvss_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    line: Optional[int] = None
    line_end: Optional[int] = None
    description: str
    evidence: Optional[str] = None
    confidence: str = "medium"   # high | medium | low
    tool_source: Optional[str] = None   # bandit | semgrep | llm


class SecurityAnalysisResult(BaseModel):
    """Output from the Security Vulnerability Agent."""
    agent: str = "SecurityVulnerabilityAgent"
    vulnerabilities: list[SecurityVulnerability] = []
    security_score: int = 100       # 0-100 (100 = no issues)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    summary: str = ""


class Remediation(BaseModel):
    """A fix recommendation linked to a finding."""
    finding_id: str
    recommendation: str
    corrected_code: Optional[str] = None
    explanation: str
    references: list[str] = []
    effort: str = "medium"   # low | medium | high


class RemediationResult(BaseModel):
    """Output from the Remediation Agent."""
    agent: str = "RemediationAgent"
    remediations: list[Remediation] = []
    summary: str = ""


class OverallRiskRating(str, Enum):
    critical = "CRITICAL"
    high = "HIGH"
    medium = "MEDIUM"
    low = "LOW"
    clean = "CLEAN"


class PRSummaryResult(BaseModel):
    """Structured PR review summary from the PR Summary Agent."""
    agent: str = "PRSummaryAgent"
    overall_risk: OverallRiskRating = OverallRiskRating.clean
    security_score: int = 100
    quality_score: int = 100
    composite_risk_score: int = 0   # 0-100
    total_findings: int = 0
    markdown_review: str = ""
    remediation_priority_list: list[str] = []
    approved: bool = False


class FullAnalysisResult(BaseModel):
    """Combined output from the entire multi-agent pipeline."""
    session_id: str
    language: str
    filename: Optional[str] = None
    code_analysis: Optional[CodeAnalysisResult] = None
    security_analysis: Optional[SecurityAnalysisResult] = None
    remediation: Optional[RemediationResult] = None
    pr_summary: Optional[PRSummaryResult] = None
    error: Optional[str] = None
