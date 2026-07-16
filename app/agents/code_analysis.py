import json
import re
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from app.llm.factory import get_fast_llm
from app.models.findings import CodeAnalysisResult
from app.agents.state import AgentState

PROMPT = """You are an expert Senior Software Engineer performing a code review.
Your task is to analyze the provided source code for code smells, design anti-patterns, complexity issues, and poor coding practices.

You have been provided with the raw source code and the output of objective static analysis tools.
Use the static analysis output to guide your review, filtering out false positives and enriching the findings with detailed descriptions and suggestions.

Provide a severity score, and grade the overall code quality.

You MUST respond with ONLY a valid raw JSON object. No markdown, no code fences, no explanation outside the JSON.
Use exactly this structure:
{{
  "agent": "CodeAnalysisAgent",
  "findings": [
    {{
      "id": "finding-001",
      "type": "code_smell",
      "category": "sql_injection",
      "severity": "high",
      "line_start": 3,
      "line_end": 3,
      "description": "Description of the issue.",
      "suggestion": "How to fix it."
    }}
  ],
  "complexity_score": {{"cyclomatic": 2, "cognitive": 3, "lines_of_code": 6, "duplication_pct": 0.0}},
  "quality_grade": "C",
  "quality_score": 55,
  "summary": "Overall summary of code quality."
}}

IMPORTANT: severity must be one of: critical, high, medium, low, informational (all lowercase).
IMPORTANT: Every finding MUST have 'id', 'type', 'category', 'severity', and 'description'.

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

async def run_code_analysis(state: AgentState) -> dict:
    """
    LangGraph node for Code Analysis.
    Takes the agent state, calls the LLM, and populates code_analysis_result.
    """
    logger.info(f"Running Code Analysis Agent for session {state.get('session_id')}")
    print(f"[CODE_ANALYSIS] Building chain...", flush=True)
    llm = get_fast_llm()
    prompt = ChatPromptTemplate.from_template(PROMPT)
    chain = prompt | llm
    
    try:
        print(f"[CODE_ANALYSIS] Calling LLM (this may take 20-60s with Ollama)...", flush=True)
        raw_response = await chain.ainvoke({
            "linter_output": json.dumps(state.get("linter_output", {})),
            "code": state.get("code", ""),
            "language": state.get("language", "python")
        })
        raw_text = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
        print(f"[CODE_ANALYSIS] LLM responded. Parsing JSON...", flush=True)
        data = _extract_json(raw_text)
        result = CodeAnalysisResult(**data)
        print(f"[CODE_ANALYSIS] Parsed OK. quality_score={result.quality_score}", flush=True)
        return {"code_analysis_result": result}
    except Exception as e:
        logger.error(f"Code Analysis Agent failed: {e}")
        print(f"[CODE_ANALYSIS] FAILED with exception: {e}", flush=True)
        # Return a graceful fallback so the pipeline continues
        return {
            "code_analysis_result": CodeAnalysisResult(
                summary=f"Code analysis encountered an error: {str(e)[:200]}"
            )
        }
