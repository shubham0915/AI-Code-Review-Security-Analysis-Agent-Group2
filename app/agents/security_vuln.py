import json
import re
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from app.llm.factory import get_llm
from app.models.findings import SecurityAnalysisResult
from app.agents.state import AgentState
from app.rag.indexer import build_or_load_index

PROMPT = """You are an expert Security Engineer performing a secure code review.
Your task is to analyze the provided source code for security vulnerabilities, specifically focusing on the OWASP Top 10 and CWE standards.

You have been provided with the raw source code, the output of objective static security analysis tools (e.g. bandit), and relevant security guidelines from our knowledge base.
Use the static analysis output and knowledge base guidelines to guide your review. Filter out false positives and enrich the findings with detailed descriptions, severity ratings, and evidence.

Provide a security score (0-100, where 100 is no issues) and classify vulnerabilities by OWASP categories.

You MUST respond with ONLY a valid raw JSON object. No markdown, no code fences, no explanation outside the JSON.
Use exactly this structure:
{{
  "agent": "SecurityVulnerabilityAgent",
  "vulnerabilities": [
    {{
      "id": "vuln-001",
      "title": "SQL Injection via string formatting",
      "owasp_category": "A03:2021 - Injection",
      "cwe_id": "89",
      "severity": "high",
      "line": 3,
      "description": "User input is concatenated directly into SQL string.",
      "evidence": "query = f\"SELECT...{{username}}\"",
      "impact": "Attacker can read, modify, or delete database records.",
      "remediation": "Use parameterized queries or ORM.",
      "confidence": "high"
    }}
  ],
  "security_score": 60,
  "critical_count": 0,
  "high_count": 1,
  "medium_count": 0,
  "low_count": 0,
  "summary": "Overall security summary here."
}}

IMPORTANT: severity must be one of: critical, high, medium, low, informational (all lowercase).
IMPORTANT: owasp_category must use the full 2021 format e.g. 'A03:2021 - Injection'.
IMPORTANT: cwe_id must be a string e.g. "89" not an integer.
IMPORTANT: Every vulnerability MUST have 'id', 'severity', and 'description'.

Security Guidelines (RAG Context):
{rag_context}

Static Analysis Output:
{linter_output}

Source Code ({language}):
```
{code}
```
"""

def _extract_json(text: str) -> dict:
    """Strips markdown fences and extracts the first JSON object from LLM output."""
    text = re.sub(r"```(?:json)?\n?", "", text).strip()
    text = text.replace("```", "").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON found in LLM output: {text[:300]}")

async def run_security_vuln(state: AgentState) -> dict:
    """
    LangGraph node for Security Vulnerability Analysis.
    Takes the agent state, queries ChromaDB for RAG context, calls the LLM.
    """
    logger.info(f"Running Security Vulnerability Agent for session {state.get('session_id')}")
    print(f"[SECURITY] Building chain...", flush=True)
    llm = get_llm()
    
    # Simple RAG: query the index with the code or linter findings to get relevant context
    rag_context = "No RAG context available."
    try:
        print(f"[SECURITY] Querying RAG index...", flush=True)
        index = build_or_load_index()
        if index:
            retriever = index.as_retriever(similarity_top_k=3)
            query_str = "Secure coding guidelines and vulnerabilities"
            linter_out = state.get("linter_output", {})
            bandit_res = linter_out.get("bandit", {})
            if isinstance(bandit_res, dict) and bandit_res.get("results"):
                issues = [r.get("issue_text", "") for r in bandit_res.get("results", [])]
                if issues:
                    query_str = " ".join(issues)
            nodes = retriever.retrieve(query_str)
            rag_context = "\n\n".join([n.text for n in nodes])
            print(f"[SECURITY] RAG context retrieved ({len(nodes)} chunks).", flush=True)
        else:
            print(f"[SECURITY] RAG index not available, continuing without context.", flush=True)
    except Exception as e:
        logger.warning(f"Failed to query RAG index, proceeding without context: {e}")
        print(f"[SECURITY] RAG query failed: {e}", flush=True)
    
    prompt = ChatPromptTemplate.from_template(PROMPT)
    chain = prompt | llm
    
    try:
        print(f"[SECURITY] Calling LLM (this may take 20-60s with Ollama)...", flush=True)
        raw_response = await chain.ainvoke({
            "rag_context": rag_context,
            "linter_output": json.dumps(state.get("linter_output", {})),
            "code": state.get("code", ""),
            "language": state.get("language", "python")
        })
        raw_text = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
        print(f"[SECURITY] LLM responded. Parsing JSON...", flush=True)
        data = _extract_json(raw_text)
        result = SecurityAnalysisResult(**data)
        print(f"[SECURITY] Parsed OK. security_score={result.security_score}", flush=True)
        return {"security_analysis_result": result}
    except Exception as e:
        logger.error(f"Security Vulnerability Agent failed: {e}")
        print(f"[SECURITY] FAILED with exception: {e}", flush=True)
        return {
            "security_analysis_result": SecurityAnalysisResult(
                summary=f"Security analysis encountered an error: {str(e)[:200]}"
            )
        }
