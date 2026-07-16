from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.code_analysis import run_code_analysis
from app.agents.security_vuln import run_security_vuln
from app.linters.python_linter import run_python_linters
from app.linters.java_linter import run_java_linters
from loguru import logger

async def run_linters(state: AgentState) -> dict:
    """
    LangGraph node to run static analysis tools before the LLMs.
    Populates the 'linter_output' field in the state.
    """
    logger.info(f"[STAGE 1/3] Running linters for session {state.get('session_id')}")
    print(f"[GRAPH][LINTERS] Starting for session {state.get('session_id')}", flush=True)
    language = state.get("language", "python").lower()
    code = state.get("code", "")
    
    try:
        if language == "python":
            results = await run_python_linters(code)
            print(f"[GRAPH][LINTERS] Python linters done. Keys: {list(results.keys())}", flush=True)
            return {"linter_output": results}
        elif language == "java":
            results = await run_java_linters(code)
            print(f"[GRAPH][LINTERS] Java linters done.", flush=True)
            return {"linter_output": results}
        else:
            print(f"[GRAPH][LINTERS] Unsupported language: {language}", flush=True)
            return {"linter_output": {"error": f"Unsupported language: {language}"}}
    except Exception as e:
        logger.error(f"Linters failed: {e}")
        print(f"[GRAPH][LINTERS] EXCEPTION: {e}", flush=True)
        return {"linter_output": {"error": str(e)}}

async def run_code_analysis_node(state: AgentState) -> dict:
    """Wrapper with logging."""
    logger.info(f"[STAGE 2/3] Code Analysis Agent for session {state.get('session_id')}")
    print(f"[GRAPH][CODE_ANALYSIS] Starting...", flush=True)
    result = await run_code_analysis(state)
    ca = result.get('code_analysis_result')
    print(f"[GRAPH][CODE_ANALYSIS] Done. quality_score={getattr(ca, 'quality_score', 'N/A')}", flush=True)
    return result

async def run_security_vuln_node(state: AgentState) -> dict:
    """Wrapper with logging."""
    logger.info(f"[STAGE 3/3] Security Vulnerability Agent for session {state.get('session_id')}")
    print(f"[GRAPH][SECURITY] Starting...", flush=True)
    result = await run_security_vuln(state)
    sa = result.get('security_analysis_result')
    print(f"[GRAPH][SECURITY] Done. security_score={getattr(sa, 'security_score', 'N/A')}", flush=True)
    return result

def build_analysis_graph():
    """
    Builds and compiles the LangGraph pipeline for code review and security analysis.
    Pipeline: run_linters -> code_analysis -> security_vuln -> END
    """
    builder = StateGraph(AgentState)
    
    # Add nodes
    builder.add_node("run_linters", run_linters)
    builder.add_node("code_analysis", run_code_analysis_node)
    builder.add_node("security_vuln", run_security_vuln_node)
    
    # Sequential pipeline: linters -> code analysis -> security -> END
    builder.set_entry_point("run_linters")
    builder.add_edge("run_linters", "code_analysis")
    builder.add_edge("code_analysis", "security_vuln")
    builder.add_edge("security_vuln", END)
    
    return builder.compile()

# Expose a compiled graph instance
analysis_graph = build_analysis_graph()
print("[GRAPH] LangGraph pipeline compiled successfully.", flush=True)
