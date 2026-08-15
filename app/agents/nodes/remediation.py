"""
About this file: remediation.py
Structure: Prompt execution logic reviewing previous findings to produce actionable repairs and refactored code.
Methods used: generate_remediation, _extract_json.
"""

import json
import re
import logfire
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate

from app.llm import get_llm
from app.models import RemediationResult
from app.agents.state import AgentState
from app.services.rag import query_index    # ← uses new services layer
from app.tracing import traceable

PROMPT = """You are an expert Secure Code Remediation Engineer.
Provide concrete, actionable fix recommendations for EVERY finding listed below.

You MUST respond with ONLY a valid raw JSON object — no markdown, no code fences, no text outside.
Use exactly this structure:
{{
  "agent": "RemediationAgent",
  "remediations": [
    {{
      "finding_id": "<string: MUST match the id from the findings list>",
      "recommendation": "<string: one-line action to fix the issue>",
      "corrected_code": "<string: rewritten code snippet, or null if no code change needed>",
      "explanation": "<string: why this fixes the issue>",
      "references": ["<string: OWASP or CWE reference>"],
      "effort": "<string: low, medium, high>"
    }}
    // IMPORTANT: If there are no findings to remediate, output an empty list [] instead.
  ],
  "summary": "<string: Brief overall summary of all remediations>"
}}

IMPORTANT: "finding_id" must exactly match the "id" field from the findings list.
IMPORTANT: "effort" must be one of: "low", "medium", "high".
IMPORTANT: Provide a remediation for EVERY finding. Set "corrected_code" to null if no code change is needed.
CRITICAL: Include the "summary" field.

Secure Coding Guidelines (RAG Context):
{rag_context}

Original Source Code ({language}):
```
{code}
```

Findings to Remediate:
{findings_json}
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


def _collect_findings(state: AgentState) -> list:
    """Flatten code analysis findings + security vulnerabilities into one list."""
    findings = []

    ca = state.get("code_analysis_result")
    if ca and ca.findings:
        for f in ca.findings:
            findings.append({
                "id": f.id,
                "type": "code_smell",
                "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                "description": f.description,
                "line_start": f.line_start,
                "line_end": f.line_end,
                "suggestion": f.suggestion,
            })

    sa = state.get("security_analysis_result")
    if sa and sa.vulnerabilities:
        for v in sa.vulnerabilities:
            findings.append({
                "id": v.id,
                "type": "security_vulnerability",
                "severity": v.severity.value if hasattr(v.severity, "value") else str(v.severity),
                "owasp_category": (
                    v.owasp_category.value
                    if v.owasp_category and hasattr(v.owasp_category, "value")
                    else str(v.owasp_category)
                ),
                "cwe_id": v.cwe_id,
                "description": v.description,
                "line": v.line,
                "remediation_hint": v.remediation,
            })

    return findings


def _build_rag_query(findings: list) -> str:
    """Prioritise security findings when building the RAG query."""
    security = [f for f in findings if f.get("type") == "security_vulnerability"]
    if security:
        descs = [f.get("description", "") for f in security[:3]]
        return "Secure coding remediation: " + " | ".join(descs)
    if findings:
        return "Code quality remediation: " + " | ".join(
            f.get("description", "") for f in findings[:3]
        )
    return "Secure coding best practices and remediation guidelines"


@traceable(name="RemediationAgent", run_type="chain")
async def run_remediation(state: AgentState) -> dict:
    """
    LangGraph node — Remediation Agent (Stage 4).
    Only reached when graph.py's conditional router found findings.
    """
    session_id = state.get("session_id")
    logger.info(f"[REMEDIATION] Starting for session {session_id}")

    findings = _collect_findings(state)
    logger.info(f"[REMEDIATION] {len(findings)} findings to remediate.")

    # Safety net: if somehow called with no findings (e.g. test bypass), exit early
    if not findings:
        return {
            "remediation_result": RemediationResult(
                remediations=[],
                summary="No findings to remediate. The code appears clean.",
            )
        }

    # ── RAG context via new services layer ────────────────────────────────────
    rag_context = "No RAG context available."
    with logfire.span("🔍 Remediation RAG Retrieval"):
        try:
            ctx = query_index(_build_rag_query(findings), top_k=4)
            if ctx:
                rag_context = ctx
                logger.info("[REMEDIATION] RAG context retrieved.")
        except Exception as e:
            logger.warning(f"[REMEDIATION] RAG query failed: {e}")

    # ── LLM chain ─────────────────────────────────────────────────────────────
    llm = get_llm()
    prompt = ChatPromptTemplate.from_template(PROMPT)
    chain = prompt | llm

    invoke_kwargs = {
        "rag_context": rag_context,
        "code": state.get("code", ""),
        "language": state.get("language", "python"),
        "findings_json": json.dumps(findings, indent=2),
    }

    raw_text = ""
    last_error = None

    for attempt in range(2):
        try:
            label = "1st attempt" if attempt == 0 else "RETRY"
            with logfire.span(f"🔧 Remediation LLM Call ({label})"):
                raw_response = await chain.ainvoke(invoke_kwargs)
                raw_text = (
                    raw_response.content
                    if hasattr(raw_response, "content")
                    else str(raw_response)
                )
            data = _extract_json(raw_text)
            result = RemediationResult(**data)
            logger.info(
                f"[REMEDIATION] OK (attempt {attempt + 1}). "
                f"remediations={len(result.remediations)}"
            )
            return {"remediation_result": result}

        except Exception as e:
            last_error = e
            if attempt == 0:
                logger.warning(f"[REMEDIATION] Parse failed attempt 1: {e}")
                invoke_kwargs = {
                    **invoke_kwargs,
                    "code": (
                        invoke_kwargs["code"]
                        + "\n\n[SYSTEM REMINDER: Respond with ONLY a valid JSON object.]"
                    ),
                }
            else:
                logger.error(f"[REMEDIATION] Parse failed attempt 2: {e}")

    return {
        "remediation_result": RemediationResult(
            remediations=[],
            summary=(
                f"[PARSE ERROR] Remediation failed after 2 attempts. "
                f"Last error: {str(last_error)[:200]}"
            ),
        )
    }