"""
About this file: linters.py
Structure: Subprocess execution wrappers for static analysis tools.
  - Python: Bandit (security), Pylint (code quality), Radon (complexity metrics), all run in parallel.
  - Java: Semgrep (enterprise-grade multi-rule static analysis engine with OWASP rulepack),
          with a lightweight regex fallback if Semgrep is unavailable.
Methods used: run_bandit, run_pylint, run_radon, run_python_linters, run_semgrep_java, run_java_linters.
"""

import tempfile
import asyncio
import json
import os
import re as _re
import sys
from typing import Dict, Any, List
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
        bandit_res, pylint_res, radon_res, semgrep_res = await asyncio.gather(
            run_bandit(temp_path),
            run_pylint(temp_path),
            run_radon(temp_path),
            _run_semgrep(code, ".py", ["p/python", "p/secrets"]),
        )
        return {
            "bandit": bandit_res, 
            "pylint": pylint_res, 
            "radon": radon_res, 
            "semgrep": semgrep_res.get("semgrep", {}),
            "heuristics": semgrep_res.get("heuristics", [])
        }
    finally:
        # Always delete the temp file — even if a tool crashes with an exception
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ─── JAVA LINTERS (SEMGREP) ───────────────────────────────────────────────────

# Mapping Semgrep severity strings → our normalized severity vocab
_SEMGREP_SEVERITY_MAP: Dict[str, str] = {
    "ERROR":   "critical",
    "WARNING": "high",
    "INFO":    "medium",
    "NOTE":    "low",
}

# Semgrep rulepacks to run for Java code.
# p/java covers the OWASP Java Security Audit ruleset (SQLi, Path Traversal, XXE,
# Deserialization, SSRF, Command Injection, Weak Crypto, Hardcoded Secrets, etc.)
_SEMGREP_JAVA_CONFIGS = ["p/java"]


def _parse_semgrep_results(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalize raw Semgrep JSON results into the uniform heuristic dict format
    expected by the rest of the pipeline (security_vuln.py fallback processor).

    Each output finding has these keys:
      - issue:    Human-readable description of the security problem.
      - severity: One of "critical" / "high" / "medium" / "low".
      - owasp:    The most recent OWASP Top 10 category string (e.g. "A03:2021 - Injection").
      - cwe:      The CWE identifier string (e.g. "CWE-89").
      - line:     Source code line number where the finding starts.
      - snippet:  The matched source code line text (capped at 200 chars).
      - rule_id:  Semgrep rule identifier (e.g. "java.lang.security.audit.formatted-sql-string").
    """
    findings = []
    for result in raw.get("results", []):
        extra = result.get("extra", {})
        metadata = extra.get("metadata", {})

        # ── Severity ────────────────────────────────────────────────────────────
        severity_raw = extra.get("severity", "INFO")
        severity = _SEMGREP_SEVERITY_MAP.get(severity_raw, "medium")

        # ── OWASP Category ──────────────────────────────────────────────────────
        owasp_list = metadata.get("owasp", [])
        # Prefer the most recent year entry (e.g. 2025 > 2021 > 2017)
        owasp_cat = "A05:2021 - Security Misconfiguration"
        for owasp_entry in reversed(owasp_list):
            if "2021" in owasp_entry or "2025" in owasp_entry:
                owasp_cat = owasp_entry
                break
        if owasp_cat == "A05:2021 - Security Misconfiguration" and owasp_list:
            owasp_cat = owasp_list[-1]

        # ── CWE ─────────────────────────────────────────────────────────────────
        cwe_list = metadata.get("cwe", [])
        if cwe_list:
            # Semgrep format: "CWE-89: Improper Neutralization..."
            # Extract just "CWE-89"
            cwe = cwe_list[0].split(":")[0].strip()
        else:
            cwe = "CWE-707"

        findings.append({
            "issue":    extra.get("message", "Security issue detected by Semgrep."),
            "severity": severity,
            "owasp":    owasp_cat,
            "cwe":      cwe,
            "line":     result.get("start", {}).get("line", 1),
            "snippet":  extra.get("lines", "")[:200],
            "rule_id":  result.get("check_id", ""),
        })

    return findings


async def _run_semgrep(code: str, suffix: str, configs: List[str]) -> Dict[str, Any]:
    """
    Run Semgrep against source code using the specified rulepacks.
    """
    semgrep_bin = _get_tool_path("semgrep")
    if not os.path.exists(semgrep_bin):
        return {
            "heuristics": [],
            "semgrep": {
                "error": "Semgrep binary not found in .venv/bin/. Install it with: pip install semgrep"
            },
        }

    # Semgrep requires a real file with the correct extension for language detection
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        cmd = [
            semgrep_bin,
            "--json",
            "--quiet",
            "--no-git-ignore",
            "--timeout", "30",
        ]
        for config in configs:
            cmd.extend(["--config", config])
        cmd.append(tmp_path)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        raw_text = stdout.decode("utf-8").strip()

        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError:
            # Semgrep can emit non-JSON warnings before the JSON block on some systems
            # Try to extract the first valid JSON object from stdout
            match = _re.search(r"\{.*\}", raw_text, _re.DOTALL)
            if match:
                raw = json.loads(match.group(0))
            else:
                return {
                    "heuristics": [],
                    "semgrep": {"error": "Failed to parse Semgrep JSON output", "stderr": stderr.decode("utf-8")[:500]},
                }

        findings = _parse_semgrep_results(raw)

        return {
            "heuristics": findings,
            "semgrep": {
                "engine":       "Semgrep OSS",
                "configs":      configs,
                "rules_matched": len(findings),
                "errors":       raw.get("errors", []),
            },
        }

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@traceable(
    name="StaticAnalysis-Java",
    run_type="tool",
)
async def run_java_linters(code: str) -> dict:
    """
    Entry point for Java static analysis.

    Uses Semgrep (enterprise-grade structural AST pattern matching engine) as the
    primary analysis backend, replacing the previous hand-written regex heuristics.

    Semgrep provides:
      - Zero-dependency analysis (no Java JDK required on the host machine)
      - Syntax-aware AST matching (immune to comment/string false positives)
      - Taint-flow tracking across variable assignments (catches indirect injections)
      - Thousands of community-verified OWASP security rules out of the box

    Falls back gracefully to an empty result set if Semgrep is not available,
    with a clear diagnostic message passed to the LLM prompt context.

    Args:
        code: Raw Java source code string.

    Returns:
        A dict with keys "heuristics" and "semgrep" (see run_semgrep_java for details).
    """
    return await _run_semgrep(code, ".java", _SEMGREP_JAVA_CONFIGS)
