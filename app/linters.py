"""
app/linters.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PURPOSE: Runs objective static analysis tools on code BEFORE the AI agents.
         The linter output is passed as context to the LLMs so they can
         focus on interpreting results instead of finding them from scratch.
         This makes the AI faster, cheaper, and more accurate.

TOOLS USED:
  Python → Bandit (security), Pylint (quality), Radon (complexity)
  Java   → PMD (stub — planned for a future milestone)

HOW IT WORKS:
  1. Write the code to a temporary file on disk
  2. Run each tool as an async subprocess (all run in parallel)
  3. Parse and return the JSON output
  4. Always clean up the temp file, even if a tool crashes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import tempfile
import asyncio
import json
import os
from typing import Dict, Any


# ─── PYTHON LINTERS ───────────────────────────────────────────────────────────

async def run_bandit(filepath: str) -> Dict[str, Any]:
    """
    Run Bandit — a security-focused Python linter.
    Detects common issues like hardcoded passwords, SQL injection patterns,
    use of dangerous functions (eval, exec, pickle), and insecure hashing.

    Returns parsed JSON output (list of security findings).
    """
    process = await asyncio.create_subprocess_exec(
        'bandit', '-f', 'json', filepath,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    try:
        return json.loads(stdout.decode('utf-8'))
    except json.JSONDecodeError:
        return {"error": "Failed to parse bandit output"}


async def run_pylint(filepath: str) -> list[Dict[str, Any]]:
    """
    Run Pylint — a general-purpose Python code quality linter.
    Detects unused imports, bad naming, missing docstrings, unreachable code,
    and hundreds of other code style and correctness issues.

    Returns a list of message objects in JSON format.
    """
    process = await asyncio.create_subprocess_exec(
        'pylint', '--output-format=json', filepath,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    try:
        return json.loads(stdout.decode('utf-8'))
    except json.JSONDecodeError:
        return [{"error": "Failed to parse pylint output"}]


async def run_radon(filepath: str) -> Dict[str, Any]:
    """
    Run Radon — a Python complexity metrics tool.
    Calculates cyclomatic complexity (how many branches does the code have?)
    for every function and class in the file.

    Lower complexity = easier to test and maintain.
    A score of A (1-5) is ideal; F (26+) means the code is extremely complex.
    """
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
    Entry point for all Python static analysis.
    Writes the code to a temp file, then runs Bandit, Pylint, and Radon
    concurrently (using asyncio.gather) so they all run in parallel
    instead of one after another.

    Args:
        code: Raw Python source code string.

    Returns:
        A dict with keys "bandit", "pylint", "radon" containing each tool's output.
        This dict is stored in the LangGraph state and passed to the AI agents.
    """
    # Write code to a named temp file (tools need a real file path, not stdin)
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as temp:
        temp.write(code)
        temp_path = temp.name

    try:
        # Run all three tools at the same time to minimize total wait time
        bandit_res, pylint_res, radon_res = await asyncio.gather(
            run_bandit(temp_path),
            run_pylint(temp_path),
            run_radon(temp_path),
        )
        return {"bandit": bandit_res, "pylint": pylint_res, "radon": radon_res}
    finally:
        # Always delete the temp file — even if a tool crashes with an exception
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ─── JAVA LINTERS ─────────────────────────────────────────────────────────────

async def run_java_linters(code: str) -> Dict[str, Any]:
    """
    Entry point for Java static analysis.

    Currently a STUB — planned to use PMD (a Java static analysis tool)
    in a future milestone. For now, the Java Security Agent relies
    entirely on the LLM and its own OWASP knowledge instead.

    Args:
        code: Raw Java source code string.

    Returns:
        A dict with a placeholder PMD message.
    """
    return {
        "pmd": {"message": "Java static analysis is deferred in this milestone. Relying purely on the LLM agent."}
    }
