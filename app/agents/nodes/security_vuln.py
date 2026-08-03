"""
About this file: security_vuln.py
Structure: Prompt formulation and parsing logic evaluating source code against Bandit vulnerability outputs and RAG context.
Methods used: analyze_security, _extract_json.
"""

import json
import re
import logfire
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate

from app.llm import get_llm
from app.models import SecurityAnalysisResult
from app.agents.state import AgentState
from app.services.rag import query_index    # ← uses new services layer
from app.tracing import traceable

PROMPT = """You are an expert Security Engineer specialising in OWASP Top 10 vulnerability analysis.
Review the provided source code and static analysis results for security vulnerabilities.

You MUST respond with ONLY a valid raw JSON object — no markdown, no code fences, no text outside the JSON.
Use exactly this structure:
{{
  "agent": "SecurityVulnerabilityAgent",
  "vulnerabilities": [
    {{
      "id": "vuln-001",
      "title": "SQL Injection via f-string",
      "owasp_category": "A03:2021 - Injection",
      "cwe_id": "CWE-89",
      "severity": "critical",
      "description": "...",
      "impact": "...",
      "line": 12,
      "evidence": "query = f'SELECT * FROM users WHERE id={{uid}}'",
      "remediation": "Use parameterized queries."
    }}
  ],
  "security_score": 40,
  "critical_count": 1,
  "high_count": 0,
  "medium_count": 0,
  "low_count": 0,
  "summary": "One critical SQL injection found."
}}

IMPORTANT: "severity" must be one of: "critical", "high", "medium", "low".
IMPORTANT: "owasp_category" must be a valid OWASP Top 10 2021 category.
CRITICAL: Include "security_score" (0-100), and all *_count fields.

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
    """
    Extracts and parses raw JSON objects from LLM markdown response strings, stripping unwanted markdown code fences.
    """
    text = re.sub(r"```(?:json)?\n?", "", text).strip().replace("```", "").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON found in output: {text[:300]}")


@traceable(name="SecurityVulnerabilityAgent", run_type="chain")
async def run_security_vuln(state: AgentState) -> dict:
    """
    LangGraph node — Security Vulnerability Agent (Stage 3).
    Detects OWASP Top 10 vulnerabilities using RAG-grounded LLM analysis.
    """
    session_id = state.get("session_id")
    language = state.get("language", "python")
    code = state.get("code", "")
    linter_out = state.get("linter_output", {})

    logger.info(f"[SECURITY] Starting for session {session_id}")

    # ── RAG context via new services layer ────────────────────────────────────
    rag_context = "No RAG context available."
    with logfire.span("🔍 Security RAG Retrieval"):
        try:
            query = f"OWASP security vulnerabilities {language} code review"
            if linter_out.get("bandit", {}).get("results"):
                first = linter_out["bandit"]["results"][0]
                query = f"{first.get('issue_text', query)} {language}"
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
                        code + "\n\n[SYSTEM REMINDER: Respond with ONLY a valid JSON object.]"
                    ),
                }
            else:
                logger.error(f"[SECURITY] Parse failed attempt 2: {e}")

    return {
        "security_analysis_result": SecurityAnalysisResult(
            vulnerabilities=[],
            security_score=0,
            summary=(
                f"[PARSE ERROR] Security analysis failed after 2 attempts. "
                f"Last error: {str(last_error)[:200]}"
            ),
        )
    }