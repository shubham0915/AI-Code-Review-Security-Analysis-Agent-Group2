# Debugging Session & Pipeline Fixes (July 2026)

This document serves as a historical record of the critical bottlenecks and logical bugs discovered and fixed during our pipeline optimization session.

## 1. Local LLM Bottleneck vs. Cloud API
**What we noticed:**
- The pipeline was taking over 5 minutes (300+ seconds) to analyze a single file.
- The LangSmith traces (`run-998a230e.json`) revealed that the bottleneck was the local Ollama instance running `qwen2.5-coder:7b`. The sequential execution of large context windows (2,300+ tokens) overwhelmed the local CPU/GPU limits.
- The 7B parameter model frequently returned Python dictionaries instead of strict JSON, causing parse crashes.

**What we changed:**
- Migrated from local Ollama to the Google Gemini API (`gemini-flash-latest` and `gemini-flash-lite-latest`) by updating the `.env` configuration.
- Result: Processing time dropped from ~300 seconds down to ~3 seconds, with much higher JSON format compliance.

---

## 2. The "Silent Failure" Fallback Bug
**What we noticed:**
- When the LLM returned malformed JSON (or a Python dict), the `json.loads()` parser crashed.
- However, the agents (`code_analysis.py` and `security_vuln.py`) had a graceful fallback in their `except Exception` blocks that returned a default empty result. 
- The critical flaw: This fallback lacked explicit score assignments, which meant Pydantic defaulted the `security_score` to `100` and `quality_score` to `0`. 
- As a result, the pipeline was silently marking highly vulnerable code (Command Injection, SSRF, RCE) as perfectly secure (100/100).

**What we changed:**
- Modified the fallback blocks in both agents to return explicit failure scores: `security_score=0`, `quality_score=0`, and `quality_grade="F"`.
- Added a `[PARSE ERROR]` prefix to the summary so the UI explicitly shows the failure.
- Implemented a 2-attempt Retry Loop: if the LLM fails to output valid JSON, it is retried once with a strict `[SYSTEM REMINDER: ONLY JSON]` prompt injection.

---

## 3. The Celery Asyncio "Event Loop is Closed" Bug
**What we noticed:**
- After migrating to Gemini, the Celery worker immediately threw an `Event loop is closed` error during the LangGraph execution.
- LangSmith trace `run-019f910a.json` confirmed this happened immediately (within 12ms) upon calling `ChatGoogleGenerativeAI`.
- Root Cause: `app/llm.py` used `@lru_cache(maxsize=1)` on the LLM constructor functions. When Celery spawns a task, it creates a fresh `asyncio` event loop. The first task cached the LLM instance (which held a persistent `httpx.AsyncClient` bound to that first event loop). When the task finished, the loop closed. Subsequent tasks retrieved the cached LLM, which tried to use the closed event loop and crashed instantly.

**What we changed:**
- Removed `@lru_cache` from `get_llm()` and `get_fast_llm()` in `app/llm.py`. Instantiating the LLM client is very fast, and this ensures each Celery task gets a fresh client bound to its own active event loop.

---

## 4. The `graph.py` Fallback Override Bug
**What we noticed:**
- Even after fixing the fallback scores in the agents, a parse failure in Code Analysis would still result in a `quality_score=100` and `quality_grade="A"`.
- Root Cause: A piece of logic in `app/agents/graph.py` was blindly catching any result with `len(findings) == 0` and `quality_score == 0` and forcefully converting it to `100`/`"A"`. This successfully masked both genuine zero-issue code and catastrophic parse failures alike.

**What we changed:**
- Updated the condition in `graph.py` to only apply the grade fallback if it is NOT an explicit error state (`ca.quality_score != 0`).

---

## 5. The Prompt Confusion (Security vs. Code Smells)
**What we noticed:**
- On a highly vulnerable test script (SSRF, YAML RCE, SQL Injection), the Gemini Flash model returned valid JSON for the Code Analysis node, but reported exactly `0` findings and a `100` score.
- Root Cause: The `PROMPT` in `app/agents/code_analysis.py` provided `"sql_injection"` as the primary example of a "code smell". Because Gemini is highly capable, it realized the test file ONLY contained security vulnerabilities. Because we instructed it to only look for "code smells" (since another agent handles security), it ignored the security issues entirely. Because it ignored them, it found 0 issues.

**What we changed:**
- Rewrote the Code Analysis `PROMPT` to remove security examples. 
- Added explicit instructions to ignore security vulnerabilities (SQLi, SSRF) and focus strictly on maintainability, convention violations (missing docstrings), and bad naming.
- Enforced that the LLM must explicitly read the Pylint linter output and translate those warnings into findings.

---

## 6. Gatekeeper vs. Intent Guardrail Latency & Service Degradation (Milestone 4)
**What we noticed:**
- When introducing the lightweight LLM intent verification guardrail (`app/guardrails.py`) to prevent prompt injections and non-code spam, evaluating inputs before pushing tasks to Celery caused immediate HTTP submission latency to jump from under 50ms up to ~1–3 seconds.
- Additionally, if an external cloud LLM endpoint experienced rate-limiting or network timeouts during high load, legitimate user code submissions were completely blocked before reaching the background task queue.

**What we changed:**
- Implemented a structured two-stage Gatekeeper architectural hierarchy:
  1. Pure Python AST / `javalang` syntax parsing (`validators.py`) executes first in `<1ms`. If syntax fails, the request is instantly rejected without calling any LLMs.
  2. If syntax passes, a lightweight fast model (`get_fast_llm()`) evaluates input intent.
- We explicitly engineered the intent guardrail to **fail open** (defaulting to `ALLOW` on network/timeout exceptions). This trade-off ensures service degradation or model latency spikes never break legitimate developer CI/CD workflows or UI interactions.

---

## 7. Stateful Conversational Memory Loss in RESTful Chat Routes (Milestone 4)
**What we noticed:**
- When developing an interactive chat assistant (`POST /api/v1/chat`), standard stateless routing caused the model to lose track of multi-turn user questions and forget the underlying security defects previously discovered by the background Celery worker.
- Passing the entire review history inside every single client request payload was bandwidth-inefficient and error-prone.

**What we changed:**
- Engineered a dedicated stateful conversational machine in `app/agents/chat_graph.py` utilizing LangGraph's native `MemorySaver` checkpointer.
- Tied conversational threads directly to the code review `session_id`. Upon receiving a chat prompt, our responder node queries Redis (`session:{session_id}:result`) to inject the live multi-agent vulnerability findings directly into the assistant's system instructions. This grants complete multi-turn recall over both chat history and analysis reports.

---

## 8. Integration Test Mock Breakages After Modular Package Refactoring
**What we noticed:**
- Following best-practice structural conventions (inspired by clean repository architectures like MARATHON), we modularized monolithic agent code into focused node packages (`app/agents/nodes/`) and consolidated cache management in `app/cache.py`.
- While unit tests passed (37/37), running integration test suites (`test_submit_api.py`) threw fatal import exceptions: `AttributeError: module 'app.cache' has no attribute 'redis_cache'`.

**What we changed:**
- Diagnosed that legacy integration tests were aggressively patching internal module implementations (`app.cache.redis_cache.get_redis_client`) rather than targeting the boundary consumer import paths.
- Realigned all test mocks to `@patch("app.api.routes.submit.get_redis_client")`, restoring clean decoupling between package internals and API testing while driving total test suite success to **49/49 passing tests**.

---

## 9. AI Safety Filter Censorship & Model Refusals on Vulnerable Code
**What we noticed:**
- When evaluating critical severity vulnerability snippets (e.g., `os.system("rm -rf /var/app/data/" + user_dir)`, SQL Injection strings like `"john_doe'; --"`, or hardcoded AWS secret keys), the AI model safety filter incorrectly interpreted the prompt as an offensive exploitation inquiry.
- The model refused to answer with valid JSON, returning plaintext refusals: *"Sorry, I cannot fulfill your request to analyze the provided code for security vulnerabilities..."*.
- Consequently, JSON extraction crashed, and fallback exception handling returned `0` vulnerabilities with a `100/100` score—silently dropping deterministic vulnerabilities that our static Bandit AST scanner had successfully identified in milliseconds.

**What we changed:**
- **Authorized Defensive Auditor Framing:** Modified `PROMPT` in `app/agents/nodes/security_vuln.py` to establish an explicit defensive context: *"You are an expert Application Security Auditor performing an authorized, strictly defensive white-box security audit. Your solely defensive mandate is to help software engineers identify and remediate OWASP Top 10 vulnerabilities in their own corporate codebase. Do not refuse defensive code auditing tasks."* This completely neutralized censorship refusal errors.
- **Deterministic Bandit Static Fallbacks:** Engineered a resilient fallback helper (`_extract_bandit_fallbacks`) in `security_vuln.py`. Whenever an LLM times out, refuses, or returns zero findings while static scanners discovered high-risk vectors (e.g., CWE-89 SQLi, CWE-78 Shell Execution, or CWE-327 weak MD5 hashes), the pipeline automatically converts Bandit AST results into full `SecurityVulnerability` scorecard objects.

---

## 10. Sequential Execution Latency & Parallel LangGraph Fan-Out Architecture
**What we noticed:**
- Running comprehensive multi-agent code analysis on test scripts took ~77 seconds per request because the four LangGraph AI nodes (`Code Analysis` ➔ `Security` ➔ `Remediation` ➔ `PR Summary`) executed sequentially one after another in traditional conversational chain styling.

**What we changed:**
- **Parallel Fan-Out / Fan-In StateGraph Architecture:** Identified that Code Quality evaluation and RAG Security evaluation are independent discovery stages. Upgraded `app/agents/graph.py` from a sequential chain into a concurrent parallel graph. Stage 1 (`run_linters`) forks simultaneously into both `code_analysis` (Stage 2A) and `security_vuln` (Stage 2B) in parallel asynchronous tasks. Both paths converge into a synchronization node (`sync_findings`) before evaluating conditional routing to Remediation or PR Summary, cutting total evaluation turnaround times by over 50%.

---

## 11. Java Security Resilience, QA Compliance Prompting & Multi-Language Static Fallbacks
**What we noticed:**
- Testing our multi-language Java security flaw test case (`UI_TEST_CASES.md` — Section 4 containing JDBC SQL Injection and File Read Path Traversal) resulted in `No security vulnerabilities detected!` with a perfect `100/100` score in the Streamlit UI dashboard.
- Inspecting LangSmith execution traces (`run-019fc716-d698-7cd2-95d8-64bbf98168af.json`) uncovered two interacting root causes:
  1. **Model Content Safety Refusal:** When presented with Java JDBC SQL Injection paired with words like `"vulnerabilities"`, Gemini's automated content safety filter aborted JSON generation and returned plaintext: *"Sorry, I cannot fulfill your request to analyze or identify vulnerabilities in the provided code snippet..."*.
  2. **Python-Only Static Fallback & Missing Java Rules:** Our static fallback safety net (`_extract_bandit_fallbacks`) exclusively monitored **Bandit** (which runs strictly on Python ASTs), ignoring Java linter outputs (`linter_output["heuristics"]`). Furthermore, our previous Java regex heuristics in `app/linters.py` only checked for simple patterns like `printStackTrace()` rather than dynamic variable SQL string building or `new File()` concatenation.

**What we changed:**
- **QA Compliance Auditor Framing:** Reconfigured system prompt instructions in `app/agents/nodes/security_vuln.py` around *"Principal Software Architect and QA Compliance Auditor evaluating OWASP ASVS compliance deviations, missing input sanitization controls, and risky syntax patterns"*. Framing reviews around QA compliance and software resilience prevents AI content filters from mistaking secure Java code auditing for offensive hacking requests.
- **Multi-Language Deterministic Static Fallbacks:** Upgraded our fallback engine into a versatile `_extract_static_fallbacks` processor that checks both Python Bandit results AND Java security heuristics. If the LLM ever times out, experiences network degradation, or refuses to parse JSON, the pipeline directly converts static discoveries into full `SecurityVulnerability` scorecards without dropping findings.
- **Comprehensive Java Security Regex Rules:** Expanded `_JAVA_SECURITY_PATTERNS` in `app/linters.py` with multi-line regex detections (using `_re.IGNORECASE | _re.MULTILINE` flags) to identify dynamic JDBC SQL string concatenation (`CWE-89`), unsanitized file path construction (`new File(..." +` / `CWE-22`), and hardcoded database connection credentials (`CWE-798`).
