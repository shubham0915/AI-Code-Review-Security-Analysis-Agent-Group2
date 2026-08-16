# Debugging Session Notes

This file serves as a historical record of significant bugs encountered during the development of the AI Code Review platform and how they were resolved. It is intended to help future maintainers understand the rationale behind specific edge-case handling in the codebase.

---

## 1. The LLM JSON Extraction Bug (Markdown Wrapping)

### The Problem
During load testing, the `CodeAnalysisAgent` and `SecurityVulnAgent` frequently failed with `JSONDecodeError`. The root cause was that LLMs (especially instruction-tuned models) have a strong tendency to wrap their JSON outputs inside markdown code blocks (e.g., ` ```json `) and often prepend conversational filler text (e.g., "Here is your analysis:"). 

Because Python's `json.loads()` expects a raw, unformatted string, these conversational wrappers caused catastrophic pipeline failures, causing the agents to crash before their data could be passed to the next LangGraph node.

### The Solution
We implemented a robust regex-based extraction pipeline in `app/agents/nodes/code_analysis.py` (`_extract_json`):
1. **Regex Cleaning**: We run `re.sub(r"```(?:json)?\n?", "", text).strip()` to hunt down and completely strip any variation of markdown backticks or the `json` language identifier.
2. **Brace Matching**: Instead of parsing the entire string, we locate the very first `{` and the very last `}`. We extract the exact substring between these braces. This effectively ignores all conversational filler text at the beginning or end of the LLM's response.
3. **Strict Prompting**: We updated the system prompts with capitalized, hard-stop instructions: `CRITICAL: You MUST include the 'summary'...`.

---

## 2. The Semgrep AWS Dummy Key Whitelist Bug

### The Problem
We decided to upgrade the Python static analysis pipeline from Bandit to Semgrep to get deep inter-procedural taint tracking. We added the `p/secrets` rulepack to detect hardcoded API keys. 
During testing, we supplied a file containing `AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"`. However, Semgrep `p/secrets` completely ignored it and returned 0 findings!

### The Solution
After investigating Semgrep's enterprise-grade rulepack behavior, we discovered that `p/secrets` actively **whitelists** known dummy/example keys (any key containing words like `EXAMPLE`, `TEST`, or `FAKE`). This is an intentional feature by Semgrep to prevent false-positive spam when developers commit unit tests. 

We validated the pipeline by replacing the dummy key with a high-entropy fake key (`AKIAJM2QGH34FGEF732Q`). Semgrep immediately flagged it as a **CRITICAL CWE-798** vulnerability and successfully injected it into the LLM's fallback context.

---

## 3. The Contradictory UI Bug (APPROVED vs BLOCKED)

### The Problem
In the React frontend (`frontend-react/src/components/ResultsPanel.tsx`), the dashboard was displaying "APPROVED" at the top, but the PR Summary agent was simultaneously flagging the code as "BLOCKED" due to Medium-severity vulnerabilities.

The root cause was a disjointed evaluation metric:
- **The Frontend** had a hardcoded string-matching heuristic: `isBlocked = overallRisk === "CRITICAL" || overallRisk === "HIGH"`. This meant that if the risk was "MEDIUM", the UI naively assumed it was safe and displayed "APPROVED".
- **The Backend (PR Agent)** had a strict, zero-tolerance policy defined in `app/agents/nodes/pr_summary.py` that blocked any deployment containing Medium risks, returning `approved: false`.

### The Solution
We stripped the naive string-matching heuristic from the React frontend. We updated `ResultsPanel.tsx` to strictly read the backend's explicit boolean flag (`isBlocked = !result.pr_summary.approved`). This guarantees that the UI state perfectly synchronizes with the LangGraph agent's executive decision, resolving the contradictory states.
