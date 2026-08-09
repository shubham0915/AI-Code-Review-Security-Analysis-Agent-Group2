"""
About this file: code_analysis.py
Structure: Prompt formulation and parsing logic evaluating source code alongside Pylint/Radon static
           analysis outputs that are now computed directly inside this agent.
Methods used: run_code_analysis, _extract_json.
"""
import json
import re
import logfire
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from app.llm import get_llm, get_fast_llm
from app.models import CodeAnalysisResult
from app.agents.state import AgentState
from app.tracing import traceable
from app.linters import run_python_linters, run_java_linters

PROMPT = """You are an expert Senior Software Engineer performing a code review.
Your task is to analyze the provided source code ONLY for code smells, design anti-patterns, complexity issues, convention violations (like missing docstrings), and poor coding practices.
Do NOT report security vulnerabilities (like SQL injection or SSRF) — another agent handles security.

You have been provided with the raw source code and the output of objective static analysis tools.
Use the static analysis output (especially Pylint convention and warning messages) to guide your review. You MUST include any missing docstrings, bad naming conventions, or unused imports found by the linters in your findings.

Provide a severity score, and grade the overall code quality.

You MUST respond with ONLY a valid raw JSON object. No markdown, no code fences, no explanation outside the JSON.
Use exactly this structure:
{{
  "agent": "CodeAnalysisAgent",
  "findings": [
    {{
      "id": "finding-001",
      "type": "code_smell",
      "category": "maintainability",
      "severity": "medium",
      "line_start": 3,
      "line_end": 5,
      "description": "Function is missing a docstring explaining its purpose.",
      "suggestion": "Add a descriptive docstring."
    }}
  ],
  "complexity_score": {{"cyclomatic": 2, "cognitive": 3, "lines_of_code": 6, "duplication_pct": 0.0}},
  "quality_grade": "C",
  "quality_score": 55,
  "summary": "Overall summary of code quality."
}}

IMPORTANT: severity must be one of: critical, high, medium, low, informational (all lowercase).
IMPORTANT: Every finding MUST have 'id', 'type', 'category', 'severity', and 'description'.
CRITICAL: You MUST include the 'summary', 'quality_score', and 'quality_grade' fields in the root JSON object, even if the findings array is empty!

Static Analysis Output:
{linter_output}

Source Code ({language}):
```
{code}
```
"""

def _extract_json(text: str) -> dict:
    """Strips markdown fences and extracts the first JSON object from LLM output."""
    # Remove ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"```(?:json)?\n?", "", text).strip()
    text = text.replace("```", "").strip()
    # Find the first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON found in LLM output: {text[:300]}")

@traceable(
    name="CodeAnalysisAgent",
    run_type="chain",
)
async def run_code_analysis(state: AgentState) -> dict:
    """
    LangGraph node for Code Analysis.
    Takes the agent state, calls the LLM, and populates code_analysis_result.
    Includes JSON parse retry logic: if the LLM returns malformed JSON on the
    first attempt, we retry once with an explicit JSON-only reminder.
    """
    logger.info(f"Running Code Analysis Agent for session {state.get('session_id')}")
    print(f"[CODE_ANALYSIS] Building chain...", flush=True)

    # ── Stage 1 (embedded): Run quality-focused linters before calling the LLM ──
    language = state.get("language", "python").lower()
    code = state.get("code", "")
    linter_out = state.get("linter_output", {}) or {}
    try:
        if language == "python":
            quality_results = await run_python_linters(code)
            # Merge into linter_output (preserve security linter keys if set)
            linter_out = {**linter_out, **quality_results}
        # Java quality linting: Semgrep handles Java in security_vuln; skip here
        logger.info(f"[CODE_ANALYSIS] Quality linters complete — language={language}")
    except Exception as e:
        logger.warning(f"[CODE_ANALYSIS] Quality linter error (non-fatal): {e}")

    llm = get_llm()
    prompt = ChatPromptTemplate.from_template(PROMPT)
    chain = prompt | llm

    invoke_kwargs = {
        "linter_output": json.dumps(linter_out),
        "code": code,
        "language": language,
    }

    raw_text = ""
    last_error = None

    for attempt in range(2):
        try:
            label = "1st attempt" if attempt == 0 else "RETRY"
            with logfire.span(f"📝 Code Analysis LLM Call ({label})"):
                raw_response = await chain.ainvoke(invoke_kwargs)

            # Handle structured responses (Pydantic model returned by mock or structured LLM)
            if isinstance(raw_response, CodeAnalysisResult):
                return {"code_analysis_result": raw_response}
            elif isinstance(raw_response, dict):
                return {"code_analysis_result": CodeAnalysisResult(**raw_response)}
            else:
                raw_text = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
                data = _extract_json(raw_text)
                result = CodeAnalysisResult(**data)
                # Inject Radon complexity metrics if available
                if "radon" in linter_out and isinstance(linter_out["radon"], dict):
                    radon = linter_out["radon"]
                    max_cc = max(
                        (b.get("complexity", 0)
                         for blocks in radon.get("cc", {}).values() if isinstance(blocks, list)
                         for b in blocks if isinstance(b, dict)),
                        default=0,
                    )
                    result.complexity_score.cyclomatic = max_cc
                    result.complexity_score.lines_of_code = sum(
                        s.get("loc", 0)
                        for s in radon.get("raw", {}).values() if isinstance(s, dict)
                    )
                logger.info(f"[CODE_ANALYSIS] OK (attempt {attempt + 1}). quality_score={result.quality_score}")
                return {"code_analysis_result": result, "linter_output": linter_out}

        except (ValueError, json.JSONDecodeError, Exception) as e:
            last_error = e
            if attempt == 0:
                logger.warning(f"[CODE_ANALYSIS] Parse failed attempt 1: {e}")
                invoke_kwargs = {
                    **invoke_kwargs,
                    "code": (
                        invoke_kwargs["code"]
                        + "\n\n[SYSTEM REMINDER: Respond with ONLY a valid JSON object.]"
                    ),
                }
            else:
                logger.error(f"[CODE_ANALYSIS] Parse failed attempt 2: {e}")

    # ── Fallback: both attempts failed — return a clear error result ──────────
    # IMPORTANT: quality_score=0 and quality_grade="F" signal that analysis FAILED,
    # NOT that the code is perfect. Never return score=100 on error.
    return {
        "code_analysis_result": CodeAnalysisResult(
            quality_score=0,
            quality_grade="F",
            summary=(
                f"[PARSE ERROR] Code analysis failed after 2 attempts. "
                f"The LLM returned malformed JSON. Last error: {str(last_error)[:200]}"
            ),
        )
    }