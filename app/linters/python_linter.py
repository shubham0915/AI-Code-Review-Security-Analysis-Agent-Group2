import tempfile
import asyncio
import json
import os
from typing import Dict, Any

async def run_bandit(filepath: str) -> Dict[str, Any]:
    process = await asyncio.create_subprocess_exec(
        'bandit', '-f', 'json', filepath,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    try:
        # Bandit returns JSON to stdout
        return json.loads(stdout.decode('utf-8'))
    except json.JSONDecodeError:
        return {"error": "Failed to parse bandit output"}

async def run_pylint(filepath: str) -> list[Dict[str, Any]]:
    process = await asyncio.create_subprocess_exec(
        'pylint', '--output-format=json', filepath,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    try:
        # Pylint returns a list of dictionaries in JSON format
        return json.loads(stdout.decode('utf-8'))
    except json.JSONDecodeError:
        return [{"error": "Failed to parse pylint output"}]

async def run_radon(filepath: str) -> Dict[str, Any]:
    process = await asyncio.create_subprocess_exec(
        'radon', 'cc', '-j', filepath,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    try:
        return json.loads(stdout.decode('utf-8'))
    except json.JSONDecodeError:
        return {"error": "Failed to parse radon output"}

async def run_python_linters(code: str) -> Dict[str, Any]:
    """
    Run static analysis tools concurrently on the given python code.
    Writes code to a temporary file, executes tools, and returns parsed JSON outputs.
    """
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as temp:
        temp.write(code)
        temp_path = temp.name
    
    try:
        bandit_task = run_bandit(temp_path)
        pylint_task = run_pylint(temp_path)
        radon_task = run_radon(temp_path)
        
        bandit_res, pylint_res, radon_res = await asyncio.gather(
            bandit_task, pylint_task, radon_task
        )
        
        return {
            "bandit": bandit_res,
            "pylint": pylint_res,
            "radon": radon_res
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
