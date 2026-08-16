"""
About this file: pr_summary.py
Structure: Prompt execution logic combining quality and security findings into an executive PR overview and risk rating.
Methods used: generate_pr_summary.
"""

import json
import re
import logfire
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from app.llm import get_fast_llm
from app.models import PRSummaryResult, OverallRiskRating
from app.agents.state import AgentState
from app.tracing import traceable

PROMPT = """You are a Senior Engineering Lead performing a final Pull Request review.
You have received the complete output of an automated AI code review pipeline.
Your task is to compile ALL findings into a single, structured PR review summary.

Scoring Rules:
- Start security_score at 100. Deduct: critical=-30, high=-15, medium=-7, low=-2 per finding.
- Start quality_score at 100. Deduct per code smell: critical=-20, high=-10, medium=-5, low=-2.
- composite_risk_score = round(0.6 * (100 - security_score) + 0.4 * (100 - quality_score))
- overall_risk: "CRITICAL" if any critical vuln, "HIGH" if any high, "MEDIUM" if any medium, "LOW" if any low, else "CLEAN".
- approved: true ONLY if overall_risk is "LOW" or "CLEAN" (zero critical/high findings).

markdown_review format:
## 🤖 AI Code Review Report
**Overall Risk:** [risk badge]
**Security Score:** X/100 | **Quality Score:** X/100

### 🚨 Critical & High Findings
[table or list of critical/high items]

### ⚠️ Medium & Low Findings
[table or list of medium/low items]

### ✅ Remediation Priority
[numbered list, most urgent first]

### 📊 Summary
[2-3 sentence summary for a developer]

You MUST respond with ONLY a valid raw JSON object. No markdown, no code fences, no explanation outside the JSON.
Use exactly this structure:
{{
  "agent": "PRSummaryAgent",
  "overall_risk": "<string: CRITICAL, HIGH, MEDIUM, LOW, or CLEAN>",
  "security_score": "<integer: 0-100>",
  "quality_score": "<integer: 0-100>",
  "composite_risk_score": "<integer: 0-100>",
  "total_findings": "<integer: total number of issues found>",
  "markdown_review": "<string: detailed markdown formatted review report>",
  "remediation_priority_list": [
    "<string: A one-sentence summary of the finding and its line number, ending with the severity>"
    // IMPORTANT: If there are no findings, output an empty list [] instead.
  ],
  "approved": false
}}

IMPORTANT: "overall_risk" must be one of: "CRITICAL", "HIGH", "MEDIUM", "LOW", "CLEAN".
IMPORTANT: All scores must be integers between 0 and 100.
CRITICAL: You MUST include ALL fields in the root JSON object.

Code Analysis Result:
{code_analysis_json}

Security Analysis Result:
{security_analysis_json}

Remediation Summary:
{remediation_summary}
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


def _compute_fallback_scores(state: AgentState) -> dict:
    """
    Compute a deterministic fallback PR summary when the LLM fails.
    This ensures the UI always gets valid data even if the LLM errors out.
    """
    code_result = state.get("code_analysis_result")
    sec_result = state.get("security_analysis_result")

    security_score = sec_result.security_score if sec_result else 100
    quality_score = code_result.quality_score if code_result else 100

    total_findings = 0
    has_critical = False
    has_high = False
    has_medium = False

    if sec_result:
        total_findings += len(sec_result.vulnerabilities)
        has_critical = sec_result.critical_count > 0
        has_high = sec_result.high_count > 0
        has_medium = sec_result.medium_count > 0

    if code_result:
        total_findings += len(code_result.findings)

    if has_critical:
        overall_risk = "CRITICAL"
    elif has_high:
        overall_risk = "HIGH"
    elif has_medium:
        overall_risk = "MEDIUM"
    elif total_findings > 0:
        overall_risk = "LOW"
    else:
        overall_risk = "CLEAN"

    composite = round(0.6 * (100 - security_score) + 0.4 * (100 - quality_score))
    approved = overall_risk in ("LOW", "CLEAN")

    return {
        "overall_risk": overall_risk,
        "security_score": security_score,
        "quality_score": quality_score,
        "composite_risk_score": max(0, min(100, composite)),
        "total_findings": total_findings,
        "approved": approved,
    }


@traceable(
    name="PRSummaryAgent",
    run_type="chain",
)
async def run_pr_summary(state: AgentState) -> dict:
    """
    LangGraph node for the PR Summary Agent (Stage 5 — final).
    Compiles all agent outputs into a structured PR review with risk score,
    markdown comment, and remediation priority list.

    Returns:
        dict with key "pr_summary_result" containing a PRSummaryResult object.
    """
    logger.info(f"Running PR Summary Agent for session {state.get('session_id')}")
    print("[PR_SUMMARY] Starting...", flush=True)

    # ── Serialize prior agent results for the prompt ──────────────────────────
    code_result = state.get("code_analysis_result")
    sec_result = state.get("security_analysis_result")
    rem_result = state.get("remediation_result")

    def _safe_dump(model):
        """Safely serialize a Pydantic model to JSON string."""
        if model is None:
            return "No data available."
        try:
            return json.dumps(model.model_dump(), indent=2)
        except Exception:  # pylint: disable=broad-exception-caught
            return str(model)

    invoke_kwargs = {
        "code_analysis_json": _safe_dump(code_result),
        "security_analysis_json": _safe_dump(sec_result),
        "remediation_summary": rem_result.summary if rem_result else "No remediation data.",
    }

    # ── Build LLM chain ───────────────────────────────────────────────────────
    llm = get_fast_llm()
    prompt = ChatPromptTemplate.from_template(PROMPT)
    chain = prompt | llm

    raw_text = ""
    last_error = None

    for attempt in range(2):
        try:
            label = "1st attempt" if attempt == 0 else "RETRY"
            with logfire.span(f"📋 PR Summary LLM Call ({label})"):
                raw_response = await chain.ainvoke(invoke_kwargs)
                raw_text = (
                    raw_response.content
                    if hasattr(raw_response, "content")
                    else str(raw_response)
                )
            data = _extract_json(raw_text)
            result = PRSummaryResult(**data)
            logger.info(
                f"[PR_SUMMARY] OK (attempt {attempt + 1}). "
                f"overall_risk={result.overall_risk}, approved={result.approved}"
            )
            return {"pr_summary_result": result}

        except (ValueError, json.JSONDecodeError, Exception) as e:  # pylint: disable=broad-exception-caught
            last_error = e
            if attempt == 0:
                logger.warning(f"[PR_SUMMARY] Parse failed attempt 1: {e}")
                invoke_kwargs = {
                    **invoke_kwargs,
                    "code_analysis_json": (
                        invoke_kwargs["code_analysis_json"]
                        + "\n\n[SYSTEM REMINDER: Respond with ONLY a valid JSON object.]"
                    ),
                }
            else:
                logger.error(f"[PR_SUMMARY] Parse failed attempt 2: {e}")

    logger.warning(
        f"[PR_SUMMARY] Using deterministic fallback for session {state.get('session_id')}"
    )

    fallback = _compute_fallback_scores(state)
    return {
        "pr_summary_result": PRSummaryResult(
            overall_risk=OverallRiskRating(fallback["overall_risk"]),
            security_score=fallback["security_score"],
            quality_score=fallback["quality_score"],
            composite_risk_score=fallback["composite_risk_score"],
            total_findings=fallback["total_findings"],
            markdown_review=(
                f"## ⚠️ PR Summary (Auto-Generated)\n\n"
                f"The PR Summary Agent could not generate a full review. "
                f"Scores have been computed directly from agent outputs.\n\n"
                f"**Overall Risk:** {fallback['overall_risk']} | "
                f"**Security Score:** {fallback['security_score']}/100 | "
                f"**Quality Score:** {fallback['quality_score']}/100\n\n"
                f"*Last error: {str(last_error)[:200]}*"
            ),
            remediation_priority_list=[],
            approved=fallback["approved"],
        )
    }
