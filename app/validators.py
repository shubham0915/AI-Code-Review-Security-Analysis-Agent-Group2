"""
app/validators.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PURPOSE: Acts as the "Gatekeeper" — the very first check before any
         AI agent ever sees the user's code.

         Step 1: DETECT what language the code is (Python or Java?)
         Step 2: VALIDATE the syntax (is it even valid code?)

         If either step fails, the pipeline halts immediately.
         Broken or unsupported code is NEVER sent to the LLM agents.
         (This rule is enforced by .agents/AGENTS.md)

SECTIONS:
  1. Language Detection  — Uses Google Magika (ML-based) to identify the language
  2. Syntax Validation   — Uses ast.parse (Python) and javalang (Java)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import ast
import os
import re
from typing import Optional

from loguru import logger

from app.models import Language, SubmissionValidationResponse, ValidationError


# ─── SECTION 1: LANGUAGE DETECTION ────────────────────────────────────────────
# Detection strategy (in priority order):
#   1. File extension (.py → python, .java → java) — most reliable
#   2. Google Magika ML model — understands code patterns
#   3. Simple keyword scan — fast fallback for tiny snippets

# Java-specific keywords that almost never appear in Python code
_JAVA_KEYWORDS = frozenset([
    "public class", "private class", "protected class",
    "public static void main", "import java.", "import javax.",
    "System.out.", "System.err.", "System.in.",
    "extends ", "implements ", "new ArrayList", "new HashMap",
    "new LinkedList", "new HashSet", "@Override", "@NotNull", "@Nullable",
    "throws ", "catch (", "finally {", "String[] args",
    "void main", "public static", "private static", "protected static",
])

# Python-specific patterns (deliberately avoiding 'import ' alone — too generic)
_PYTHON_KEYWORDS = frozenset([
    "def ",         # Python function definition keyword
    "elif ",        # Python-only (Java uses 'else if')
    "__init__",     # Python class constructor magic method
    "self.",        # Python instance method first argument
    "lambda ",      # Python anonymous functions
    "yield ",       # Python generators
    "if __name__",  # Python main guard pattern
    "#!/usr/bin/env python",  # Python shebang line
    "# -*-",        # Python encoding declaration comment
    "print(",       # Python 3 print function
    "from __future__",  # Python future imports
])


def detect_language(code: str, filename: Optional[str] = None) -> Language:
    """
    Determine whether the submitted code is Python or Java.

    Never returns Language.auto — always resolves to a concrete language
    or Language.unsupported if we cannot identify it.

    Args:
        code: The raw source code string.
        filename: Optional file name hint (e.g. "main.py" or "App.java").

    Returns:
        Language enum value.
    """
    # STEP 1 — File extension is the most reliable signal
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".py":
            return Language.python
        if ext == ".java":
            return Language.java
        # Explicitly reject common but unsupported languages
        if ext in [".js", ".ts", ".html", ".css", ".cpp", ".c", ".go", ".rs", ".rb", ".php", ".sh", ".json"]:
            logger.warning(f"Unsupported file extension detected: {ext}")
            return Language.unsupported

    # STEP 2 — Google Magika ML model (most accurate for ambiguous code)
    try:
        from magika import Magika
        m = Magika()
        res = m.identify_bytes(code.encode("utf-8", errors="replace"))
        label = res.output.label.lower()
        logger.debug(f"Magika ML detected label: {label}")

        if label == "python":
            return Language.python
        if label == "java":
            return Language.java
        # If Magika is confident it's something else (like 'javascript'), reject it
        if label not in ["txt", "empty", "unknown", "python", "java"]:
            logger.warning(f"Magika ML rejected unsupported language: {label}")
            return Language.unsupported
    except Exception as e:
        # Magika not installed or crashed — fall through to keyword scan
        logger.error(f"Magika detection error: {e}")

    # STEP 3 — Fast naive keyword fallback for tiny snippets Magika might label "txt"
    if "public class" in code or "System.out" in code or "import java." in code:
        return Language.java
    if "def " in code or "import " in code or "print(" in code:
        return Language.python

    # Could not identify — reject
    return Language.unsupported


# ─── SECTION 2: SYNTAX VALIDATION ─────────────────────────────────────────────
# These functions actually parse the code to check if it's syntactically correct.
# They run BEFORE the LLM agents to ensure we never waste tokens on broken code.

def _validate_python(code: str) -> SubmissionValidationResponse:
    """
    Validate Python syntax using the built-in ast.parse() function.
    This is instant (microseconds) and 100% accurate for Python.
    """
    try:
        ast.parse(code)
        return SubmissionValidationResponse(valid=True, errors=[], detail="Python syntax is valid.")
    except SyntaxError as e:
        # Capture the exact line number so the user knows where the error is
        error = ValidationError(field="code", message=f"SyntaxError at line {e.lineno}: {e.msg}")
        return SubmissionValidationResponse(valid=False, errors=[error], detail="Python syntax validation failed.")
    except Exception as e:
        error = ValidationError(field="code", message=str(e))
        return SubmissionValidationResponse(valid=False, errors=[error])


def _validate_java_heuristic(code: str) -> SubmissionValidationResponse:
    """
    Lightweight heuristic Java validator.
    Used as a fallback when the javalang parser is unavailable or crashes.
    Checks for the two most common structural errors:
      1. Missing class/interface declaration
      2. Unbalanced curly braces or parentheses
    """
    errors: list[ValidationError] = []

    # A valid Java file must have at least one class, interface, or enum
    if not re.search(r"\b(class|interface|enum)\s+\w+", code):
        errors.append(ValidationError(
            field="code",
            message="No class, interface, or enum declaration found. Is this valid Java?",
        ))

    # Check for unbalanced braces — a very common mistake
    open_braces = code.count("{")
    close_braces = code.count("}")
    if open_braces != close_braces:
        errors.append(ValidationError(
            field="code",
            message=f"Unbalanced braces: {open_braces} opening '{{' vs {close_braces} closing '}}'.",
        ))

    # Check for unbalanced parentheses
    open_parens = code.count("(")
    close_parens = code.count(")")
    if open_parens != close_parens:
        errors.append(ValidationError(
            field="code",
            message=f"Unbalanced parentheses: {open_parens} '(' vs {close_parens} ')'.",
        ))

    if errors:
        return SubmissionValidationResponse(valid=False, errors=errors, detail="Java heuristic pre-validation failed.")
    return SubmissionValidationResponse(valid=True, errors=[], detail="Java heuristic pre-check passed (javac unavailable).")


def _validate_java(code: str) -> SubmissionValidationResponse:
    """
    Validate Java syntax using the 'javalang' pure-Python parser.
    This gives us exact line/column numbers for errors without needing
    the Java JDK (javac) installed on the server.

    Falls back to heuristic checks if javalang is unavailable.
    """
    errors: list[ValidationError] = []
    import javalang  # noqa: PLC0415 — imported here to avoid slow startup

    try:
        javalang.parse.parse(code)
        return SubmissionValidationResponse(valid=True, errors=[], detail="Java syntax is valid (parsed by javalang).")
    except javalang.parser.JavaSyntaxError as e:
        # Extract the exact position of the syntax error
        line_no = e.at.position.line if e.at and e.at.position else None
        col_no = e.at.position.column if e.at and e.at.position else None
        errors.append(ValidationError(
            field="code",
            message=f"SyntaxError at line {line_no}: {e.description}",
            line=line_no,
            column=col_no,
        ))
        # Also run heuristic checks to catch additional structural issues
        heuristic = _validate_java_heuristic(code)
        errors.extend(heuristic.errors)
        return SubmissionValidationResponse(
            valid=False, errors=errors,
            detail=f"Java parsing failed with {len(errors)} error(s).",
        )
    except Exception as e:
        logger.error(f"javalang validation error: {e}")
        # If javalang itself crashes, fall back to the simpler heuristic validator
        return _validate_java_heuristic(code)


def validate_code(code: str, language: Language) -> SubmissionValidationResponse:
    """
    PUBLIC ENTRY POINT — called by the API submit routes.

    Routes to the correct language-specific validator.
    If code is empty, or language is unsupported, returns an error immediately.

    Args:
        code: Raw source code string.
        language: The resolved language (must not be Language.auto — detect first).

    Returns:
        SubmissionValidationResponse with valid=True or valid=False + error details.
    """
    # Guard: never process an empty submission
    if not code or not code.strip():
        return SubmissionValidationResponse(
            valid=False,
            errors=[ValidationError(field="code", message="Code is empty.")],
            detail="Empty code submission.",
        )

    if language == Language.python:
        result = _validate_python(code)
    elif language == Language.java:
        result = _validate_java(code)
    elif language == Language.unsupported:
        # Language was detected but is not Python or Java — reject it
        result = SubmissionValidationResponse(
            valid=False,
            errors=[ValidationError(
                field="language",
                message="Unsupported language detected. Please write code in Java or Python only.",
            )],
            detail="Unsupported Language.",
        )
    else:
        # Language.auto should have been resolved before calling this function
        result = SubmissionValidationResponse(
            valid=True,
            detail=f"No syntax validator for language '{language}'. Passing through.",
        )

    logger.debug(f"Validation: lang={language.value} valid={result.valid} errors={len(result.errors)}")
    return result
