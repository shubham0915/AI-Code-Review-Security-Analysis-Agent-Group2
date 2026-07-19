"""
app/models/report.py — Pydantic models for exportable review reports.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from .findings import FullAnalysisResult


class ExportFormat(str, Enum):
    markdown = "markdown"
    json = "json"
    pdf = "pdf"


class ReportMetadata(BaseModel):
    session_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    filename: Optional[str] = None
    language: str = "unknown"
    report_version: str = "1.0"
    tool_name: str = "AI Code Review & Security Analysis Agent"


class ExportRequest(BaseModel):
    session_id: str
    format: ExportFormat = ExportFormat.markdown
    include_corrected_code: bool = True
    include_raw_linter_output: bool = False


class ReportDocument(BaseModel):
    metadata: ReportMetadata
    analysis: FullAnalysisResult
    export_format: ExportFormat = ExportFormat.json
