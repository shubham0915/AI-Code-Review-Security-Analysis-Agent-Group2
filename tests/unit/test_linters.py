import pytest
import json
from unittest.mock import AsyncMock, patch
from app.linters import run_bandit, run_pylint, run_radon, run_python_linters, run_java_linters

@pytest.mark.asyncio
@patch("app.linters.asyncio.create_subprocess_exec")
async def test_run_bandit(mock_exec):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (json.dumps({"results": []}).encode('utf-8'), b"")
    mock_exec.return_value = mock_process
    
    result = await run_bandit("test.py")
    assert "results" in result

@pytest.mark.asyncio
@patch("app.linters.asyncio.create_subprocess_exec")
async def test_run_pylint(mock_exec):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (json.dumps([{"type": "warning"}]).encode('utf-8'), b"")
    mock_exec.return_value = mock_process
    
    result = await run_pylint("test.py")
    assert isinstance(result, list)
    assert len(result) == 1

@pytest.mark.asyncio
@patch("app.linters.asyncio.create_subprocess_exec")
async def test_run_radon(mock_exec):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (json.dumps({"test.py": []}).encode('utf-8'), b"")
    mock_exec.return_value = mock_process
    
    result = await run_radon("test.py")
    assert "cc" in result
    assert "raw" in result

@pytest.mark.asyncio
@patch("app.linters.run_radon")
@patch("app.linters.run_pylint")
@patch("app.linters.run_bandit")
async def test_run_python_linters(mock_bandit, mock_pylint, mock_radon):
    mock_bandit.return_value = {"results": []}
    mock_pylint.return_value = []
    mock_radon.return_value = {}
    
    code = "def foo(): pass"
    res = await run_python_linters(code)
    
    assert "bandit" in res
    assert "pylint" in res
    assert "radon" in res
    assert res["bandit"] == {"results": []}

@pytest.mark.asyncio
async def test_run_java_linters():
    res = await run_java_linters("public class Test {}")
    # Verify the new Semgrep-based output structure
    assert "heuristics" in res, "Expected 'heuristics' key in Java linter output"
    assert "semgrep" in res, "Expected 'semgrep' metadata key in Java linter output"
    assert isinstance(res["heuristics"], list), "'heuristics' should be a list"
    assert isinstance(res["semgrep"], dict), "'semgrep' metadata should be a dict"
