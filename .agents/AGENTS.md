# AI Code Review Agent — Project Rules & Architectural Guidelines

## 1. The Gatekeeper Pattern (Syntax Validation)
**Rule:** NEVER pass code to the AI / LLM Agents if it fails syntax validation or is in an unsupported language.
**Context:** Our language detection (Magika) and syntax validation (`javalang` / `ast`) act as a strict gatekeeper before placing tasks on the Celery queue. 
**Why:** Sending broken or unsupported code to LLMs wastes API tokens, slows down the system (AI takes 10s vs AST takes 1ms), and causes the AI to hallucinate analysis on broken logic.
**Implementation:** If `_local_validate` or `api_validate` returns `valid=False`, the pipeline MUST halt immediately and return the error to the user without invoking any AI agent layers.
