"""
app/models.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PURPOSE: Defines all Pydantic data models used across the project.
         Think of this file as the "blueprint" for every piece of data
         that flows through the system — from the user's first request
         to the final analysis report.

SECTIONS:
  1. Session Models   — What the user submits and what we immediately return
  2. Agent Outputs    — What each AI agent produces (code smells, vulns, etc.)
  3. Report Models    — Models for exporting/downloading the final report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ─── SECTION 1: SESSION & SUBMISSION MODELS ───────────────────────────────────
# These models handle the "front door" of the system:
# what comes IN from the user, and what goes OUT immediately.

class Language(str, Enum):
    """The programming language of the submitted code."""
    python = "python"
    java = "java"
    auto = "auto"           # Let the system detect it automatically
    unsupported = "unsupported"


class TaskStatus(str, Enum):
    """The lifecycle state of an analysis job in the background queue."""
    queued = "queued"       # Waiting in the Celery queue
    running = "running"     # Actively being processed by the agents
    completed = "completed" # All agents finished successfully
    failed = "failed"       # Something went wrong — check error_message


class CodeSubmissionRequest(BaseModel):
    """
    The JSON body the user sends when pasting code via the API.
    Example: POST /api/v1/submit/paste
    """
    code: str = Field(..., min_length=1, description="Raw source code to analyze")
    language: Language = Field(Language.auto, description="Programming language")
    filename: Optional[str] = Field(None, description="Optional filename hint")

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "import sqlite3\ndef get_user(uid):\n    conn = sqlite3.connect('db')\n    return conn.execute(f'SELECT * FROM users WHERE id={uid}').fetchall()",
                "language": "python",
                "filename": "example.py",
            }
        }
    }


class SubmissionResponse(BaseModel):
    """
    Returned instantly after a valid code submission.
    Contains the session_id that the frontend uses to poll for results.
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.queued
    language: Language = Language.auto
    filename: Optional[str] = None
    lines_of_code: int = 0
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_seconds: int = Field(45, description="Estimated processing time in seconds")
    message: str = "Code submitted successfully. Analysis queued."

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "status": "queued",
                "language": "python",
                "lines_of_code": 4,
                "estimated_seconds": 45,
                "message": "Code submitted successfully. Analysis queued.",
            }
        }
    }


class TaskStatusResponse(BaseModel):
    """
    Returned when the frontend polls GET /api/v1/status/{session_id}.
    Shows how far along the analysis job is.
    """
    session_id: str
    status: TaskStatus
    progress_pct: int = Field(0, ge=0, le=100, description="Completion percentage")
    current_stage: Optional[str] = Field(None, description="Current agent stage")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ValidationError(BaseModel):
    """A single syntax error found during pre-validation (before the AI agents run)."""
    field: str          # Which field caused the error (usually "code" or "language")
    message: str        # Human-readable description of the error
    line: Optional[int] = None      # Line number where the syntax error occurred
    column: Optional[int] = None    # Column number (if available)


class SubmissionValidationResponse(BaseModel):
    """
    Returned when code fails syntax validation.
    The pipeline halts here — broken code is NEVER sent to the AI agents.
    (See: Gatekeeper Pattern in .agents/AGENTS.md)
    """
    valid: bool = False
    errors: list[ValidationError] = []
    detail: str = "Submission validation failed."


# ─── SECTION 2: AGENT OUTPUT MODELS ───────────────────────────────────────────
# These are the data structures each AI agent populates and returns.
# They are chained together as the pipeline progresses.

class Severity(str, Enum):
    """
    Standardized severity scale used by all agents.
    Maps directly to color-coding in the frontend UI.
    """
    critical = "critical"       # Immediately exploitable (e.g. unauthenticated SQLi)
    high = "high"               # Serious risk, likely exploitable
    medium = "medium"           # Real issue but limited exploitability
    low = "low"                 # Best-practice violation, minimal real-world risk
    informational = "informational"  # Style note, no security or correctness impact


class OwaspCategory(str, Enum):
    """OWASP Top 10 2021 categories used to classify security vulnerabilities."""
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
    """
    A single code quality issue found by the Code Analysis Agent.
    Examples: overly complex function, bad naming, missing error handling.
    """
    # id is auto-generated if the LLM forgets to include one
    id: Optional[str] = None
    type: str = "code_smell"
    category: Optional[str] = None     # e.g. "Complexity", "Maintainability"
    severity: Severity = Severity.medium
    line_start: Optional[int] = None   # Where the problematic code begins
    line_end: Optional[int] = None     # Where the problematic code ends
    description: str = ""              # What the problem is
    snippet: Optional[str] = None      # The actual code that triggered this finding
    suggestion: Optional[str] = None   # How to fix it

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v: Any):
        # LLMs sometimes return "HIGH" or "High" — normalize to lowercase
        if isinstance(v, str):
            return v.lower()
        return v

    @model_validator(mode="after")
    def set_defaults(self):
        # Auto-fill missing id and category so the frontend never gets null values
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.category:
            self.category = self.type
        return self


class ComplexityScore(BaseModel):
    """
    Objective code complexity metrics calculated from static analysis tools.
    Used by the Code Analysis Agent to give context to the LLM.
    """
    cyclomatic: int = 0             # Number of independent paths through the code
    cognitive: int = 0              # How hard the code is for a human to understand
    lines_of_code: int = 0
    duplication_pct: float = 0.0    # What % of the code is duplicated
    maintainability_index: Optional[float] = None  # 0-100 score (100 = perfectly maintainable)


class CodeAnalysisResult(BaseModel):
    """
    The complete output from the Code Analysis Agent.
    Contains all detected code smells and an overall quality grade.
    """
    agent: str = "CodeAnalysisAgent"
    findings: list[CodeSmell] = []          # List of individual code quality issues
    complexity_score: ComplexityScore = ComplexityScore()
    quality_grade: str = "N/A"              # A-F letter grade (like a school grade)
    quality_score: int = 0                  # Numeric score 0-100
    summary: str = ""                       # Human-readable paragraph summary


class SecurityVulnerability(BaseModel):
    """
    A single security vulnerability found by the Security Agent.
    Always includes an OWASP category and CWE ID where possible.
    """
    # id is auto-generated if the LLM forgets to include one
    id: Optional[str] = None
    owasp_category: Optional[OwaspCategory] = None  # e.g. "A03:2021 - Injection"
    cwe_id: Optional[str] = None            # e.g. "CWE-89" for SQL Injection
    severity: Severity = Severity.medium
    cvss_score: Optional[float] = Field(None, ge=0.0, le=10.0)  # Industry-standard 0-10 risk score
    line: Optional[int] = None              # Line number of the vulnerable code
    line_end: Optional[int] = None
    title: Optional[str] = None
    description: str = ""
    evidence: Optional[str] = None          # The actual vulnerable code snippet
    confidence: str = "medium"              # How confident is the agent? high/medium/low
    tool_source: Optional[str] = None       # Which tool found it: "bandit", "semgrep", or "llm"
    remediation: Optional[str] = None       # Quick one-line fix suggestion
    impact: Optional[str] = None            # What damage could an attacker do?

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v: Any):
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator("cwe_id", mode="before")
    @classmethod
    def coerce_cwe_id(cls, v: Any):
        # LLMs sometimes return CWE as an integer (89) instead of a string ("89")
        if v is not None:
            return str(v)
        return v

    @field_validator("owasp_category", mode="before")
    @classmethod
    def normalize_owasp(cls, v: Any):
        """
        Makes OWASP category flexible. Accepts all of these formats:
        "A03", "A3", "A3: Injection", "A03:2021 - Injection"
        """
        if v is None:
            return v
        if not isinstance(v, str):
            return None
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
        # Last resort: match by keyword in the string
        v_lower = v.lower()
        if "injection" in v_lower:
            return OwaspCategory.A03.value
        if "access control" in v_lower or "authorization" in v_lower:
            return OwaspCategory.A01.value
        if "crypto" in v_lower:
            return OwaspCategory.A02.value
        if "auth" in v_lower:
            return OwaspCategory.A07.value
        return None  # Discard values we cannot recognize

    @model_validator(mode="after")
    def set_defaults(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        return self


class SecurityAnalysisResult(BaseModel):
    """
    The complete output from the Security Vulnerability Agent.
    Contains all found vulnerabilities and an overall security score.
    """
    agent: str = "SecurityVulnerabilityAgent"
    vulnerabilities: list[SecurityVulnerability] = []
    security_score: int = 100   # Starts at 100 (clean), drops for each finding
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    summary: str = ""


class Remediation(BaseModel):
    """
    A concrete fix recommendation produced by the Remediation Agent.
    Always linked to a specific finding by its ID.
    """
    finding_id: str             # Points to either a CodeSmell.id or SecurityVulnerability.id
    recommendation: str         # Short one-line action to take
    corrected_code: Optional[str] = None  # The actual fixed code snippet or diff
    explanation: str            # Why this fix works and what it prevents
    references: list[str] = []  # Links to OWASP, CWE, or RAG knowledge base chunks
    effort: str = "medium"      # How hard is this fix to implement: "low", "medium", "high"


class RemediationResult(BaseModel):
    """The complete output from the Remediation Agent."""
    agent: str = "RemediationAgent"
    remediations: list[Remediation] = []
    summary: str = ""


class OverallRiskRating(str, Enum):
    """
    The final top-level risk verdict for the entire submission.
    Determined by the PR Summary Agent based on all findings.
    """
    critical = "CRITICAL"   # Stop everything — do not merge
    high = "HIGH"           # Serious issues — fix before merging
    medium = "MEDIUM"       # Address soon — technical debt
    low = "LOW"             # Minor issues — can merge with notes
    clean = "CLEAN"         # No significant issues found


class PRSummaryResult(BaseModel):
    """
    The final structured output from the PR Summary Agent.
    This is what gets displayed as the top-level review card in the frontend.
    """
    agent: str = "PRSummaryAgent"
    overall_risk: OverallRiskRating = OverallRiskRating.clean
    security_score: int = 100           # 0-100, combines all security findings
    quality_score: int = 100            # 0-100, combines all code quality findings
    composite_risk_score: int = 0       # 0-100 overall danger score (higher = worse)
    total_findings: int = 0
    markdown_review: str = ""           # Full PR comment ready to paste into GitHub/GitLab
    remediation_priority_list: list[str] = []  # Ordered list: fix these first
    approved: bool = False              # True only when there are zero critical/high findings


class FullAnalysisResult(BaseModel):
    """
    The master result object that combines outputs from ALL agents.
    Stored in Redis after the pipeline finishes.
    Retrieved by the frontend via GET /api/v1/result/{session_id}.
    """
    session_id: str
    language: str
    filename: Optional[str] = None
    code_analysis: Optional[CodeAnalysisResult] = None      # From Code Analysis Agent
    security_analysis: Optional[SecurityAnalysisResult] = None  # From Security Agent
    remediation: Optional[RemediationResult] = None         # From Remediation Agent
    pr_summary: Optional[PRSummaryResult] = None            # From PR Summary Agent
    error: Optional[str] = None                             # Set only if the pipeline crashed


# ─── SECTION 3: REPORT EXPORT MODELS ──────────────────────────────────────────
# These models handle downloading/exporting a completed analysis report.

class ExportFormat(str, Enum):
    """Supported formats for downloading a report."""
    markdown = "markdown"   # Good for pasting into GitHub PR comments
    json = "json"           # Good for integration with other tools
    pdf = "pdf"             # Good for sharing with non-technical stakeholders


class ReportMetadata(BaseModel):
    """Header information attached to every exported report."""
    session_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    filename: Optional[str] = None
    language: str = "unknown"
    report_version: str = "1.0"
    tool_name: str = "AI Code Review & Security Analysis Agent"


class ExportRequest(BaseModel):
    """The request body for POST /api/v1/report/export."""
    session_id: str
    format: ExportFormat = ExportFormat.markdown
    include_corrected_code: bool = True         # Include the fixed code snippets?
    include_raw_linter_output: bool = False     # Include raw bandit/pylint JSON? (verbose)


class ReportDocument(BaseModel):
    """The complete exportable document combining metadata and full analysis."""
    metadata: ReportMetadata
    analysis: FullAnalysisResult
    export_format: ExportFormat = ExportFormat.json
