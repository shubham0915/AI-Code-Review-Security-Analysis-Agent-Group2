"""
app/models/findings.py — Pydantic models for agent analysis findings.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator


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

    # id and category are auto-generated if the LLM omits them
    id: Optional[str] = None
    type: str = "code_smell"
    category: Optional[str] = None
    severity: Severity = Severity.medium
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    description: str = ""
    snippet: Optional[str] = None
    suggestion: Optional[str] = None

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v: Any):
        if isinstance(v, str):
            return v.lower()
        return v

    @model_validator(mode="after")
    def set_defaults(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.category:
            self.category = self.type
        return self


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
    quality_grade: str = "N/A"  # A-F
    quality_score: int = 0  # 0-100
    summary: str = ""


class SecurityVulnerability(BaseModel):
    """A single security vulnerability finding."""

    # id is auto-generated if the LLM omits it
    id: Optional[str] = None
    owasp_category: Optional[OwaspCategory] = None
    cwe_id: Optional[str] = None
    severity: Severity = Severity.medium
    cvss_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    line: Optional[int] = None
    line_end: Optional[int] = None
    title: Optional[str] = None
    description: str = ""
    evidence: Optional[str] = None
    confidence: str = "medium"  # high | medium | low
    tool_source: Optional[str] = None  # bandit | semgrep | llm
    remediation: Optional[str] = None
    impact: Optional[str] = None

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v: Any):
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator("cwe_id", mode="before")
    @classmethod
    def coerce_cwe_id(cls, v: Any):
        """LLMs sometimes return CWE as integer (89) instead of string ('89')."""
        if v is not None:
            return str(v)
        return v

    @field_validator("owasp_category", mode="before")
    @classmethod
    def normalize_owasp(cls, v: Any):
        """Accept 'A03', 'A3', 'A1: Injection', full form, etc."""
        if v is None:
            return v
        if not isinstance(v, str):
            return None  # discard non-strings
        # Map by prefix — handle both zero-padded (A01) and unpadded (A1)
        owasp_map = [
            (["A01", "A1"], OwaspCategory.A01),
            (["A02", "A2"], OwaspCategory.A02),
            (["A03", "A3"], OwaspCategory.A03),
            (["A04", "A4"], OwaspCategory.A04),
            (["A05", "A5"], OwaspCategory.A05),
            (["A06", "A6"], OwaspCategory.A06),
            (["A07", "A7"], OwaspCategory.A07),
            (["A08", "A8"], OwaspCategory.A08),
            (["A09", "A9"], OwaspCategory.A09),
            (["A10"], OwaspCategory.A10),
        ]
        for prefixes, category in owasp_map:
            if any(v.upper().startswith(p) for p in prefixes):
                return category.value
        # Try keyword matching as last resort
        v_lower = v.lower()
        if "injection" in v_lower:
            return OwaspCategory.A03.value
        if "access control" in v_lower or "authorization" in v_lower:
            return OwaspCategory.A01.value
        if "crypto" in v_lower:
            return OwaspCategory.A02.value
        if "auth" in v_lower:
            return OwaspCategory.A07.value
        return None  # discard unrecognized values

    @model_validator(mode="after")
    def set_defaults(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        return self


class SecurityAnalysisResult(BaseModel):
    """Output from the Security Vulnerability Agent."""

    agent: str = "SecurityVulnerabilityAgent"
    vulnerabilities: list[SecurityVulnerability] = []
    security_score: int = 100  # 0-100 (100 = no issues)
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
    effort: str = "medium"  # low | medium | high


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
    composite_risk_score: int = 0  # 0-100
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
