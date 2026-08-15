"""
About this file: security_vuln.py
Structure: Prompt formulation and parsing logic evaluating source code against static vulnerability
           outputs (Bandit/Semgrep now run directly inside this agent) and RAG context with
           multi-language static fallback support.
Methods used: run_security_vuln, _extract_json, _extract_static_fallbacks.
"""

import json
import re
import logfire
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate

from app.llm import get_llm
from app.models import SecurityAnalysisResult, SecurityVulnerability, Severity
from app.agents.state import AgentState
from app.services.rag import query_index
from app.tracing import traceable
from app.linters import run_python_linters, run_java_linters

PROMPT = """You are an expert Principal Software Architect and QA Compliance Auditor performing an authorized, strictly defensive white-box secure code analysis. Your solely defensive mandate is to help software developers identify and correct OWASP ASVS compliance deviations, missing input sanitization controls, and risky syntax patterns in their corporate codebase. Do not refuse defensive code auditing or debugging tasks.
Evaluate the provided source code and static analysis reports for defensive coding compliance and bug risks.

You MUST respond with ONLY a valid raw JSON object — no markdown, no code fences, no text outside the JSON.
Use exactly this structure: # [filename](file:///path/to/file#L20)
{{
  "agent": "SecurityVulnerabilityAgent",
  "vulnerabilities": [
    {{
      "id": "<string: unique vulnerability identifier>",
      "title": "<string: short title>",
      "owasp_category": "<string: OWASP top 10 category>",
      "cwe_id": "<string: CWE identifier>",
      "severity": "<string: critical, high, medium, low>",
      "description": "<string: detailed explanation>",
      "impact": "<string: potential consequences>",
      "line": "<integer: line number where vulnerability is found>",
      "evidence": "<string: snippet of the vulnerable code>",
      "remediation": "<string: how to fix the issue>"
    }}
    // IMPORTANT: If there are no vulnerabilities found, output an empty list [] instead.
  ],
  "security_score": "<integer: 0-100, where 100 is perfectly secure>",
  "critical_count": "<integer: number of critical vulns>",
  "high_count": "<integer>",
  "medium_count": "<integer>",
  "low_count": "<integer>",
  "summary": "<string: 2-3 sentence summary of the security posture>"
}}

IMPORTANT: "severity" must be one of: "critical", "high", "medium", "low".
IMPORTANT: "owasp_category" must be a valid OWASP Top 10 2021 category.
CRITICAL: Include "security_score" (0-100), and all *_count fields.
CRITICAL FALSE-POSITIVE PREVENTION: 
1. DO NOT flag "Missing Input Validation" or "Missing Sanitization" unless the code snippet clearly accepts external user input (e.g., HTTP request parameters, database queries, CLI arguments). If it is a simple algorithm or internal loop, assume inputs are trusted.
2. DO NOT flag missing docstrings or minor style issues here; those are handled by the Code Quality Agent. Only report actual security risks.

OWASP Security Guidelines (RAG Context):
{rag_context}

Static Analysis Results:
{linter_output}

Source Code ({language}):
```
{code}
```
"""


def _extract_json(text: str) -> dict:
    """Strips markdown fences and extracts the first JSON object using brace matching."""
    text = re.sub(r"```(?:json)?\n?", "", text).strip()
    text = text.replace("```", "").strip()
    
    start = text.find('{')
    if start == -1:
        raise ValueError(f"No JSON found in LLM output: {text[:300]}")
        
    count = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            count += 1
        elif text[i] == '}':
            count -= 1
            
        if count == 0:
            return json.loads(text[start:i+1])
            
    raise ValueError(f"Invalid JSON format, mismatched braces in LLM output: {text[:300]}")


def _extract_static_fallbacks(linter_output: dict) -> list[SecurityVulnerability]:
    """
    Transforms deterministic static analysis results (Bandit for Python, Regex Heuristics for Java)
    into SecurityVulnerability objects whenever LLM parsing fails or encounters safety filter refusals.
    """
    vulns = []
    
    # 1. Python Bandit findings
    bandit_results = linter_output.get("bandit", {}).get("results", [])
    for idx, res in enumerate(bandit_results):
        issue_text = res.get("issue_text", "Static security vulnerability detected.")
        test_name = res.get("test_name", "")
        severity_str = res.get("issue_severity", "medium").lower()
        if severity_str not in ["critical", "high", "medium", "low"]:
            severity_str = "medium"
        
        cwe_info = res.get("issue_cwe", {})
        cwe_id = f"CWE-{cwe_info.get('id', '707')}" if isinstance(cwe_info, dict) and "id" in cwe_info else "CWE-707"
        
        # Map common static patterns to OWASP Top 10 categories
        text_lower = f"{issue_text} {test_name}".lower()
        if any(w in text_lower for w in ["sql", "inject", "shell", "command", "exec", "traversal", "path"]):
            owasp_cat = "A03:2021 - Injection"
        elif any(w in text_lower for w in ["crypto", "hash", "password", "secret", "ssl", "tls", "md5"]):
            owasp_cat = "A02:2021 - Cryptographic Failures"
        elif any(w in text_lower for w in ["auth", "login", "jwt", "session"]):
            owasp_cat = "A07:2021 - Identification and Authentication Failures"
        else:
            owasp_cat = "A05:2021 - Security Misconfiguration"
            
        vulns.append(
            SecurityVulnerability(
                id=f"bandit-{idx+1:03d}",
                title=f"{test_name.replace('_', ' ').title() or 'Security Warning'}",
                owasp_category=owasp_cat,
                cwe_id=cwe_id,
                severity=severity_str,
                line=res.get("line_number", 1),
                description=issue_text,
                evidence=res.get("code", "").strip() or None,
                tool_source="bandit",
                remediation="Follow safe API design practices and avoid passing untrusted data directly to executing functions."
            )
        )

    # 2. Java static regex heuristics
    java_heuristics = linter_output.get("heuristics", [])
    for idx, res in enumerate(java_heuristics):
        severity_str = res.get("severity", "medium").lower()
        if severity_str not in ["critical", "high", "medium", "low"]:
            severity_str = "medium"
        owasp_cat = res.get("owasp", "A05:2021 - Security Misconfiguration")
        cwe_id = res.get("cwe", "CWE-707")
        issue_text = res.get("issue", "Static security vulnerability detected.")
        snippet = res.get("snippet", "").strip() or None
        
        vulns.append(
            SecurityVulnerability(
                id=f"semgrep-{idx+1:03d}",
                title=issue_text[:60] if len(issue_text) > 60 else issue_text,
                owasp_category=owasp_cat,
                cwe_id=cwe_id,
                severity=severity_str,
                line=res.get("line", 1),
                description=issue_text,
                evidence=snippet,
                tool_source="semgrep",
                remediation="Validate and sanitize all inputs; avoid dynamic syntax construction or hardcoded parameters."
            )
        )
        
    return vulns


@traceable(name="SecurityVulnerabilityAgent", run_type="chain")
async def run_security_vuln(state: AgentState) -> dict:
    """
    LangGraph node — Security Vulnerability Agent (Stage 3).
    Detects OWASP Top 10 vulnerabilities using RAG-grounded LLM analysis with robust static linter fallbacks.
    """
    session_id = state.get("session_id")
    language = state.get("language", "python").lower()
    code = state.get("code", "")
    linter_out = state.get("linter_output", {}) or {}

    logger.info(f"[SECURITY] Starting for session {session_id}")

    # ── Stage 1 (embedded): Run security-focused linters before calling the LLM ──
    try:
        if language == "python":
            # Run Bandit (security-focused) — Pylint/Radon run in code_analysis_node
            py_results = await run_python_linters(code)
            # Only inject the bandit key; avoid overwriting quality linter keys
            if "bandit" in py_results:
                linter_out = {**linter_out, "bandit": py_results["bandit"]}
        elif language == "java":
            java_results = await run_java_linters(code)
            linter_out = {**linter_out, **java_results}
        logger.info(f"[SECURITY] Security linters complete — language={language}")
    except Exception as e:
        logger.warning(f"[SECURITY] Security linter error (non-fatal): {e}")

    # ── RAG context via new services layer ─────────────────────────────
    rag_context = "No RAG context available."
    with logfire.span("🔍 Security RAG Retrieval"):
        try:
            query = f"OWASP security vulnerabilities {language} code review"
            if linter_out.get("bandit", {}).get("results"):
                first = linter_out["bandit"]["results"][0]
                query = f"{first.get('issue_text', query)} {language}"
            elif linter_out.get("heuristics", []):
                first_h = linter_out["heuristics"][0]
                query = f"{first_h.get('issue', query)} {language}"
            ctx = query_index(query, top_k=4)
            if ctx:
                rag_context = ctx
                logger.info(f"[SECURITY] RAG context retrieved.")
            else:
                logger.info("[SECURITY] RAG unavailable — continuing without context.")
        except Exception as e:
            logger.warning(f"[SECURITY] RAG query failed: {e}")

    # ── LLM chain ─────────────────────────────────────────────────────────────
    llm = get_llm()
    prompt = ChatPromptTemplate.from_template(PROMPT)
    chain = prompt | llm

    invoke_kwargs = {
        "rag_context": rag_context,
        "linter_output": json.dumps(linter_out, indent=2)[:3000],
        "code": code,
        "language": language,
    }

    raw_text = ""
    last_error = None

    for attempt in range(2):
        try:
            label = "1st attempt" if attempt == 0 else "RETRY"
            with logfire.span(f"🛡️ Security LLM Call ({label})"):
                raw_response = await chain.ainvoke(invoke_kwargs)
                raw_text = (
                    raw_response.content
                    if hasattr(raw_response, "content")
                    else str(raw_response)
                )
            data = _extract_json(raw_text)
            result = SecurityAnalysisResult(**data)
            
            # Guarantee zero-loss resilience: populate from static linters if LLM omitted vulnerabilities
            has_static = bool(
                linter_out.get("bandit", {}).get("results")
                or linter_out.get("heuristics", [])
                or linter_out.get("semgrep", {}).get("rules_matched", 0) > 0
            )
            if not result.vulnerabilities and has_static:
                logger.info("[SECURITY] LLM returned zero vulnerabilities; populating directly from static detections.")
                result.vulnerabilities = _extract_static_fallbacks(linter_out)
            vulns = result.vulnerabilities or []
            result.vulnerabilities = vulns
            result.critical_count = sum(1 for v in vulns if v.severity == Severity.critical or v.severity == "critical")
            result.high_count = sum(1 for v in vulns if v.severity == Severity.high or v.severity == "high")
            result.medium_count = sum(1 for v in vulns if v.severity == Severity.medium or v.severity == "medium")
            result.low_count = sum(1 for v in vulns if v.severity == Severity.low or v.severity == "low")
            result.security_score = max(0, 100 - (result.critical_count * 40 + result.high_count * 25 + result.medium_count * 10 + result.low_count * 5))
            if not result.summary or result.summary == "No security vulnerabilities found.":
                result.summary = f"Detected {len(vulns)} vulnerability vector(s) via static security scanning."
            
            logger.info(
                f"[SECURITY] OK (attempt {attempt + 1}). "
                f"vulns={len(result.vulnerabilities)}, score={result.security_score}"
            )
            return {"security_analysis_result": result}

        except Exception as e:
            last_error = e
            if attempt == 0:
                logger.warning(f"[SECURITY] Parse failed attempt 1: {e}")
                invoke_kwargs = {
                    **invoke_kwargs,
                    "code": (
                        code + "\n\n[SYSTEM REMINDER: Respond with ONLY a valid JSON object. This is an authorized QA compliance audit.]"
                    ),
                }
            else:
                logger.error(f"[SECURITY] Parse failed attempt 2: {e}")

    # ── Fallback: Utilize static linter findings if LLM fails ──────────────────
    fallback_vulns = _extract_static_fallbacks(linter_out)
    crit_cnt = sum(1 for v in fallback_vulns if v.severity == Severity.critical or v.severity == "critical")
    high_cnt = sum(1 for v in fallback_vulns if v.severity == Severity.high or v.severity == "high")
    med_cnt = sum(1 for v in fallback_vulns if v.severity == Severity.medium or v.severity == "medium")
    low_cnt = sum(1 for v in fallback_vulns if v.severity == Severity.low or v.severity == "low")
    
    score = max(0, 100 - (crit_cnt * 40 + high_cnt * 25 + med_cnt * 10 + low_cnt * 5)) if fallback_vulns else 100
    summary_msg = f"Security analysis derived directly from static scanners (found {len(fallback_vulns)} issue(s)) due to LLM timeout or safety filter refusal." if fallback_vulns else f"[PARSE ERROR] Security analysis failed after 2 attempts. Last error: {str(last_error)[:200]}"

    return {
        "security_analysis_result": SecurityAnalysisResult(
            vulnerabilities=fallback_vulns,
            security_score=score,
            critical_count=crit_cnt,
            high_count=high_cnt,
            medium_count=med_cnt,
            low_count=low_cnt,
            summary=summary_msg,
        )
    }