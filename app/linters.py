"""
About this file: linters.py
Structure: Subprocess execution wrappers for external CLI linters including Pylint and Bandit, parsing output to structured findings.
Methods used: run_pylint, run_bandit, run_linters.
"""

import tempfile
import asyncio
import json
import os
import sys
from typing import Dict, Any
from app.tracing import traceable

def _get_tool_path(tool_name: str) -> str:
    """Resolve the absolute path to a tool in the current Python environment (.venv/bin)."""
    return os.path.join(os.path.dirname(sys.executable), tool_name)


# ─── PYTHON LINTERS ───────────────────────────────────────────────────────────

async def run_bandit(filepath: str) -> Dict[str, Any]:
    """
    Run Bandit — a security-focused Python linter.
    Detects common issues like hardcoded passwords, SQL injection patterns,
    use of dangerous functions (eval, exec, pickle), and insecure hashing.

    Returns parsed JSON output (list of security findings).
    """
    process = await asyncio.create_subprocess_exec(
        _get_tool_path('bandit'), '-f', 'json', filepath,
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
        _get_tool_path('pylint'), '--output-format=json', filepath,
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
    cc_process = await asyncio.create_subprocess_exec(
        _get_tool_path('radon'), 'cc', '-j', filepath,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    raw_process = await asyncio.create_subprocess_exec(
        _get_tool_path('radon'), 'raw', '-j', filepath,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout_cc, _ = await cc_process.communicate()
    stdout_raw, _ = await raw_process.communicate()
    try:
        return {
            "cc": json.loads(stdout_cc.decode('utf-8')),
            "raw": json.loads(stdout_raw.decode('utf-8'))
        }
    except json.JSONDecodeError:
        return {"error": "Failed to parse radon output"}


@traceable(
    name="StaticAnalysis-Python",
    run_type="tool",
)
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

import re as _re

# Regex patterns for common Java security anti-patterns.
# These are lightweight heuristics — not a replacement for PMD/SpotBugs,
# but they give the LLM Security Agent something concrete to work with
# without requiring a Java JDK on the host machine.
_JAVA_SECURITY_PATTERNS = [
    {
        "pattern": _re.compile(r'String\s+\w*[Pp]assword\w*\s*=\s*"[^"]+"', _re.MULTILINE),
        "issue": "Hardcoded password string literal detected",
        "severity": "HIGH",
        "owasp": "A02:2021 - Cryptographic Failures",
        "cwe": "CWE-798",
    },
    {
        "pattern": _re.compile(r'\.executeQuery\s*\(\s*"[^"]*"\s*\+', _re.MULTILINE),
        "issue": "Potential SQL Injection — string concatenation in SQL query",
        "severity": "CRITICAL",
        "owasp": "A03:2021 - Injection",
        "cwe": "CWE-89",
    },
    {
        "pattern": _re.compile(r'Statement\.execute\w*\s*\([^)]*\+', _re.MULTILINE),
        "issue": "Potential SQL Injection — dynamic SQL via Statement (use PreparedStatement)",
        "severity": "CRITICAL",
        "owasp": "A03:2021 - Injection",
        "cwe": "CWE-89",
    },
    {
        "pattern": _re.compile(r'printStackTrace\(\)', _re.MULTILINE),
        "issue": "Stack trace printed to stdout — may expose internal paths and class names",
        "severity": "LOW",
        "owasp": "A09:2021 - Security Logging and Monitoring Failures",
        "cwe": "CWE-209",
    },
    {
        "pattern": _re.compile(r'Runtime\.getRuntime\(\)\.exec\(', _re.MULTILINE),
        "issue": "OS command execution via Runtime.exec() — potential command injection",
        "severity": "HIGH",
        "owasp": "A03:2021 - Injection",
        "cwe": "CWE-78",
    },
    {
        "pattern": _re.compile(r'MessageDigest\.getInstance\("MD5"\)', _re.MULTILINE),
        "issue": "Use of MD5 — weak cryptographic hash, do not use for security purposes",
        "severity": "MEDIUM",
        "owasp": "A02:2021 - Cryptographic Failures",
        "cwe": "CWE-327",
    },
    {
        "pattern": _re.compile(r'MessageDigest\.getInstance\("SHA-1"\)', _re.MULTILINE),
        "issue": "Use of SHA-1 — deprecated cryptographic hash, prefer SHA-256 or higher",
        "severity": "MEDIUM",
        "owasp": "A02:2021 - Cryptographic Failures",
        "cwe": "CWE-327",
    },
    {
        "pattern": _re.compile(r'new\s+URL\s*\([^)]*request\.|new\s+URL\s*\([^)]*param', _re.MULTILINE),
        "issue": "Potential SSRF — URL constructed from user-controlled input",
        "severity": "HIGH",
        "owasp": "A10:2021 - Server-Side Request Forgery",
        "cwe": "CWE-918",
    },
    {
        "pattern": _re.compile(r'System\.out\.println\s*\([^)]*[Pp]assword', _re.MULTILINE),
        "issue": "Password or sensitive data may be logged to stdout",
        "severity": "MEDIUM",
        "owasp": "A09:2021 - Security Logging and Monitoring Failures",
        "cwe": "CWE-532",
    },
]


@traceable(
    name="StaticAnalysis-Java",
    run_type="tool",
)
async def run_java_linters(code: str) -> dict:
    """
    Entry point for Java static analysis.

    Runs lightweight regex heuristics to detect common Java security anti-patterns
    (SQL injection, hardcoded secrets, weak cryptography, command injection, SSRF).

    This provides the LLM Security Agent with concrete, structured findings without
    requiring a Java JDK or PMD installation on the host machine.

    Note: For production-grade Java analysis, integrate PMD or SpotBugs via subprocess
    (planned for a future milestone when Java JDK availability can be assumed).

    Args:
        code: Raw Java source code string.

    Returns:
        A dict with key "heuristics" containing a list of detected issues,
        and key "pmd" with a status note.
    """
    findings = []
    lines = code.splitlines()

    for rule in _JAVA_SECURITY_PATTERNS:
        for match in rule["pattern"].finditer(code):
            # Compute line number from character offset
            line_num = code[: match.start()].count("\n") + 1
            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else ""
            findings.append({
                "issue": rule["issue"],
                "severity": rule["severity"],
                "owasp": rule["owasp"],
                "cwe": rule["cwe"],
                "line": line_num,
                "snippet": snippet[:120],  # Cap snippet length
            })

    return {
        "heuristics": findings,
        "pmd": {
            "message": (
                f"PMD subprocess integration is planned for a future milestone. "
                f"Regex heuristics detected {len(findings)} potential issue(s)."
            )
        },
    }

