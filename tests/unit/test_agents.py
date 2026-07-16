import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage

from app.models.findings import CodeAnalysisResult, SecurityAnalysisResult
from app.agents.state import AgentState
from app.agents.code_analysis import run_code_analysis
from app.agents.security_vuln import run_security_vuln

@pytest.fixture
def sample_state() -> AgentState:
    return {
        "session_id": "123",
        "code": "def foo(): pass",
        "language": "python",
        "linter_output": {"pylint": []},
        "code_analysis_result": None,
        "security_analysis_result": None
    }

@pytest.mark.asyncio
@patch("app.agents.code_analysis.get_fast_llm")
async def test_run_code_analysis(mock_get_llm, sample_state):
    # Mock LLM response to return a valid JSON string that matches CodeAnalysisResult
    mock_llm = AsyncMock()
    valid_json = json.dumps({
        "agent": "CodeAnalysisAgent",
        "findings": [],
        "complexity_score": {
            "cyclomatic": 1,
            "cognitive": 1,
            "lines_of_code": 10,
            "duplication_pct": 0.0
        },
        "quality_grade": "A",
        "quality_score": 95,
        "summary": "Looks good"
    })
    
    # Langchain's RunnableSequence will call ainvoke on the LLM which returns an AIMessage
    mock_llm.ainvoke.return_value = AIMessage(content=valid_json)
    
    # The | operator creates a RunnableSequence. We mock the __or__ or just mock the LLM.
    # Actually, the parser handles AIMessage.
    
    # For a robust test without relying on Langchain's internal piping logic in tests, 
    # we can patch the chain's ainvoke directly:
    with patch("langchain_core.runnables.RunnableSequence.ainvoke", new_callable=AsyncMock) as mock_chain_ainvoke:
        mock_chain_ainvoke.return_value = CodeAnalysisResult(summary="Looks good", quality_score=95)
        
        result = await run_code_analysis(sample_state)
        
        assert "code_analysis_result" in result
        assert isinstance(result["code_analysis_result"], CodeAnalysisResult)
        assert result["code_analysis_result"].summary == "Looks good"


@pytest.mark.asyncio
@patch("app.agents.security_vuln.get_llm")
@patch("app.agents.security_vuln.build_or_load_index")
async def test_run_security_vuln(mock_index, mock_get_llm, sample_state):
    mock_index.return_value = None # Disable RAG for simplicity in this test
    
    with patch("langchain_core.runnables.RunnableSequence.ainvoke", new_callable=AsyncMock) as mock_chain_ainvoke:
        mock_chain_ainvoke.return_value = SecurityAnalysisResult(summary="No vulnerabilities", security_score=100)
        
        result = await run_security_vuln(sample_state)
        
        assert "security_analysis_result" in result
        assert isinstance(result["security_analysis_result"], SecurityAnalysisResult)
        assert result["security_analysis_result"].security_score == 100
