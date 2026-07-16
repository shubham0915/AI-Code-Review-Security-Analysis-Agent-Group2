# Milestone 2 — Bug Report & Resolution Log

**Project:** AI Code Review & Security Analysis Agent  
**Milestone:** Milestone 2 — Multi-Agent Pipeline (LangGraph + Celery)  
**Date:** 2026-07-16  
**Author:** Group 2

---

## Overview

During the implementation and live testing of the Milestone 2 multi-agent pipeline, we discovered and resolved **7 critical bugs** that caused the analysis to silently hang or produce incorrect results. All bugs were identified by instrumenting the code with `print()` tracing statements and reading Celery/LangGraph execution logs.

---

## Bug #1 — Broken LangGraph Fan-Out Topology

**File:** `app/agents/graph.py`  
**Severity:** 🔴 Critical (caused pipeline to hang indefinitely)

### Problem
The original LangGraph pipeline used a "fan-out" topology where the `run_linters` node had two outgoing edges — one to `code_analysis` and one to `security_vuln`, both pointing to `END`:

```
run_linters ──> code_analysis ──> END
            └─> security_vuln ──> END
```

LangGraph does **not** support this pattern without the `Send` API for true parallel fan-out. Both agents started simultaneously at the same timestamp but the event loop could not resolve both `END` paths, causing the pipeline to **deadlock indefinitely** — the task never moved from `queued` to `completed`.

### Evidence
```
15:34:33.835 | INFO | Running Code Analysis Agent for session test-debug-001
15:34:34.095 | INFO | Running Security Vulnerability Agent for session test-debug-001
# Both running at same time — no output after this for 3+ minutes
```

### Fix
Changed to a **sequential pipeline**:

```python
# BEFORE (broken fan-out)
builder.add_edge("run_linters", "code_analysis")
builder.add_edge("run_linters", "security_vuln")
builder.add_edge("code_analysis", END)
builder.add_edge("security_vuln", END)

# AFTER (sequential — correct)
builder.add_edge("run_linters", "code_analysis")
builder.add_edge("code_analysis", "security_vuln")
builder.add_edge("security_vuln", END)
```

---

## Bug #2 — `PydanticOutputParser` Failing on Ollama Markdown-Wrapped JSON

**Files:** `app/agents/code_analysis.py`, `app/agents/security_vuln.py`  
**Severity:** 🔴 Critical (all LLM outputs silently failing)

### Problem
Both agents used LangChain's `PydanticOutputParser` which injects a complex JSON schema into the prompt and expects the LLM to return a raw JSON string. Ollama models (especially `qwen2.5-coder:7b`) routinely wrap their responses in markdown code fences:

````
```json
{ "agent": "CodeAnalysisAgent", ... }
```
````

The `PydanticOutputParser` cannot parse this format and raises an exception. The exception was silently caught and returned an empty fallback result — making it impossible to diagnose from the outside.

### Fix
Replaced `PydanticOutputParser` with a direct LLM call and a custom `_extract_json()` function:

```python
def _extract_json(text: str) -> dict:
    """Strips markdown fences and extracts the first JSON object from LLM output."""
    text = re.sub(r"```(?:json)?\n?", "", text).strip()
    text = text.replace("```", "").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON found in LLM output: {text[:300]}")
```

The chain was simplified to `prompt | llm` and the output parsed manually.

---

## Bug #3 — Pydantic Enum Case Mismatch (`"MEDIUM"` vs `"medium"`)

**File:** `app/models/findings.py`  
**Severity:** 🟠 High (all findings dropped from results)

### Problem
The `Severity` enum was defined with lowercase values:

```python
class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
```

However, Ollama's `qwen2.5-coder:7b` consistently outputs uppercase severity strings (`"MEDIUM"`, `"HIGH"`, `"LOW"`). Pydantic's strict enum validation raised a `ValidationError` for every finding, causing the entire findings list to be silently dropped.

### Evidence
```
findings.0.severity
  Input should be 'critical', 'high', 'medium', 'low' or 'informational'
  [type=enum, input_value='MEDIUM', input_type=str]
```

### Fix
Added a `@field_validator(mode="before")` to normalize severity to lowercase before validation:

```python
@field_validator("severity", mode="before")
@classmethod
def normalize_severity(cls, v: Any):
    if isinstance(v, str):
        return v.lower()
    return v
```

---

## Bug #4 — Missing Required Fields (`id`, `category`) in LLM Output

**Files:** `app/models/findings.py`, `app/agents/code_analysis.py`  
**Severity:** 🟠 High (all code smell findings discarded)

### Problem
The `CodeSmell` model declared `id` and `category` as required fields with no default values. The LLM frequently omitted these fields from the JSON output (it doesn't understand which schema fields are required vs optional). This caused all findings to fail Pydantic validation.

### Evidence
```
findings.0.id       - Field required [type=missing]
findings.0.category - Field required [type=missing]
```

### Fix
1. Made `id` and `category` optional with `None` defaults.
2. Added a `@model_validator(mode="after")` that auto-generates a UUID-based `id` and falls back `category` to `type` if missing:

```python
id: Optional[str] = None
category: Optional[str] = None

@model_validator(mode="after")
def set_defaults(self):
    if not self.id:
        self.id = str(uuid.uuid4())[:8]
    if not self.category:
        self.category = self.type
    return self
```

---

## Bug #5 — `cwe_id` Integer Type Coercion

**File:** `app/models/findings.py`  
**Severity:** 🟡 Medium (security vulnerabilities failing validation)

### Problem
The `SecurityVulnerability` model declared `cwe_id: Optional[str]`. However, the LLM returned CWE IDs as integers (`89` instead of `"89"`), causing a Pydantic `string_type` validation error.

### Evidence
```
vulnerabilities.0.cwe_id
  Input should be a valid string [type=string_type, input_value=89, input_type=int]
```

### Fix
Added a type-coercion validator:

```python
@field_validator("cwe_id", mode="before")
@classmethod
def coerce_cwe_id(cls, v: Any):
    if v is not None:
        return str(v)
    return v
```

---

## Bug #6 — OWASP Category Format Mismatch

**File:** `app/models/findings.py`  
**Severity:** 🟡 Medium (OWASP classification dropped)

### Problem
The `OwaspCategory` enum expected the full 2021 format (e.g., `"A03:2021 - Injection"`). The LLM output various non-standard formats:
- `"A1: Injection"` (old OWASP format, unpadded)
- `"A03"` (short form)
- `"A3"` (short form without zero-padding)
- `"Injection"` (keyword only)

All of these caused Pydantic validation to discard the OWASP category silently.

### Fix
Rewrote the `normalize_owasp` validator to handle all observed formats with prefix matching and keyword fallback:

```python
@field_validator("owasp_category", mode="before")
@classmethod
def normalize_owasp(cls, v: Any):
    owasp_map = [
        (["A01", "A1"], OwaspCategory.A01),
        (["A02", "A2"], OwaspCategory.A02),
        (["A03", "A3"], OwaspCategory.A03),
        ...
    ]
    for prefixes, category in owasp_map:
        if any(v.upper().startswith(p) for p in prefixes):
            return category.value
    # Keyword fallback
    if "injection" in v.lower():
        return OwaspCategory.A03.value
    ...
```

---

## Bug #7 — `{username}` in Prompt Treated as LangChain Template Variable

**File:** `app/agents/security_vuln.py`  
**Severity:** 🟠 High (Security agent always failing)

### Problem
The prompt template included an example JSON with:
```json
"evidence": "query = f\"SELECT...{username}\""
```

LangChain's `ChatPromptTemplate.from_template()` scans the **entire prompt string** for `{variable}` patterns and expects them all to be provided as inputs. It detected `{username}` and required it as a mandatory input variable, raising:

```
Input to ChatPromptTemplate is missing variables {'username'}.
Expected: ['code', 'language', 'linter_output', 'rag_context', 'username']
```

### Fix
Escaped the braces in the prompt example using double curly braces `{{}}`, which LangChain renders as literal `{}`:

```python
# BEFORE (broken)
"evidence": "query = f\"SELECT...{username}\""

# AFTER (correct — double braces escape the template substitution)
"evidence": "query = f\"SELECT...{{username}}\""
```

---

## Bug #8 — `asyncio.run()` Incompatibility Inside Celery Workers

**File:** `app/tasks/analysis.py`  
**Severity:** 🟡 Medium (potential crash on some Celery configurations)

### Problem
The Celery task used `asyncio.run()` to execute the async LangGraph pipeline. In some Celery worker configurations (especially with `gevent` or `eventlet` pools), a running event loop already exists and `asyncio.run()` raises a `RuntimeError: This event loop is already running`.

### Fix
Added defensive loop detection with a `nest_asyncio` fallback:

```python
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
        final_state = loop.run_until_complete(analysis_graph.ainvoke(initial_state))
    else:
        final_state = asyncio.run(analysis_graph.ainvoke(initial_state))
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        final_state = loop.run_until_complete(analysis_graph.ainvoke(initial_state))
    finally:
        loop.close()
```

Also added `nest_asyncio>=1.6.0` to `requirements.txt`.

---

## Summary Table

| # | Bug | File | Severity | Root Cause | Fix Strategy |
|---|-----|------|----------|------------|--------------|
| 1 | LangGraph fan-out deadlock | `graph.py` | 🔴 Critical | Wrong graph topology | Sequential pipeline |
| 2 | PydanticOutputParser + Ollama | `code_analysis.py`, `security_vuln.py` | 🔴 Critical | Markdown fences in LLM output | Custom `_extract_json()` |
| 3 | Severity enum case mismatch | `findings.py` | 🟠 High | LLM outputs uppercase | `field_validator` lowercase normalizer |
| 4 | Missing `id` and `category` fields | `findings.py` | 🟠 High | LLM omits optional schema fields | Auto-generate with `model_validator` |
| 5 | `cwe_id` int vs string | `findings.py` | 🟡 Medium | LLM returns integer CWE IDs | Type coercion validator |
| 6 | OWASP category format mismatch | `findings.py` | 🟡 Medium | LLM uses legacy/short OWASP codes | Multi-format prefix + keyword normalizer |
| 7 | `{username}` as template variable | `security_vuln.py` | 🟠 High | Single braces in prompt example | Escape with `{{username}}` |
| 8 | `asyncio.run()` in Celery | `analysis.py` | 🟡 Medium | Potential conflicting event loop | Defensive loop detection + `nest_asyncio` |

---

## Verification

After all fixes, a clean end-to-end pipeline test produced:

```
STAGE 1/3 Linters       ✅  bandit + pylint + radon completed in < 1s
STAGE 2/3 Code Analysis ✅  quality_score=55, grade=C, 1 finding
STAGE 3/3 Security      ✅  security_score=60, 1 vulnerability (SQL Injection, A03:2021, HIGH)

CODE SUMMARY  → "The code has a high risk of SQL injection and lacks documentation."
SECURITY SUMM → "The code contains a SQL injection vulnerability due to direct concatenation of user input."
FIRST VULN    → id=vuln-001  severity=HIGH  category=A03:2021 - Injection
```
