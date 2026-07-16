from typing import TypedDict, Optional, Dict, Any
from app.models.findings import CodeAnalysisResult, SecurityAnalysisResult

class AgentState(TypedDict):
    session_id: str
    code: str
    language: str
    linter_output: Dict[str, Any]
    code_analysis_result: Optional[CodeAnalysisResult]
    security_analysis_result: Optional[SecurityAnalysisResult]
