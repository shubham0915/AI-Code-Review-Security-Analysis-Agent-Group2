"""
app/utils/code_validator.py — Syntax validation for Python and Java.

Python: uses ast.parse (standard library, zero overhead)
Java:   uses heuristic brace/bracket balance + keyword checks
        (full javac validation requires JDK; we do a lightweight pre-check)
"""
from __future__ import annotations

import ast
import re
from typing import Optional

from loguru import logger

from app.models.session import Language, SubmissionValidationResponse, ValidationError


# ─────────────────────────────────────────────────────────────────────────────
# Python Validator
# ─────────────────────────────────────────────────────────────────────────────
def _validate_python(code: str) -> SubmissionValidationResponse:
    try:
        ast.parse(code)
        return SubmissionValidationResponse(valid=True, errors=[], detail="Python syntax is valid.")
    except SyntaxError as e:
        error = ValidationError(
            field="code",
            message=f"SyntaxError at line {e.lineno}: {e.msg}",
        )
        return SubmissionValidationResponse(
            valid=False,
            errors=[error],
            detail="Python syntax validation failed.",
        )
    except Exception as e:
        error = ValidationError(field="code", message=str(e))
        return SubmissionValidationResponse(valid=False, errors=[error])


# ─────────────────────────────────────────────────────────────────────────────
# Java Validator (lightweight heuristic)
# ─────────────────────────────────────────────────────────────────────────────
def _validate_java(code: str) -> SubmissionValidationResponse:
    errors: list[ValidationError] = []

    # 1. Must have at least one class declaration
    if not re.search(r'\b(class|interface|enum)\s+\w+', code):
        errors.append(ValidationError(
            field="code",
            message="No class, interface, or enum declaration found. Is this valid Java?",
        ))

    # 2. Brace balance check
    open_braces = code.count("{")
    close_braces = code.count("}")
    if open_braces != close_braces:
        errors.append(ValidationError(
            field="code",
            message=f"Unbalanced braces: {open_braces} opening '{{' vs {close_braces} closing '}}'.",
        ))

    # 3. Parenthesis balance
    open_parens = code.count("(")
    close_parens = code.count(")")
    if open_parens != close_parens:
        errors.append(ValidationError(
            field="code",
            message=f"Unbalanced parentheses: {open_parens} '(' vs {close_parens} ')'.",
        ))

    # 4. Check for obvious encoding issues
    try:
        code.encode("utf-8")
    except UnicodeEncodeError as e:
        errors.append(ValidationError(field="code", message=f"Encoding error: {e}"))

    if errors:
        return SubmissionValidationResponse(
            valid=False,
            errors=errors,
            detail="Java syntax pre-validation failed.",
        )
    return SubmissionValidationResponse(valid=True, errors=[], detail="Java syntax pre-check passed.")


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────
def validate_code(code: str, language: Language) -> SubmissionValidationResponse:
    """
    Validate source code syntax.

    Args:
        code: Raw source code string.
        language: Detected or specified language (must not be Language.auto).

    Returns:
        SubmissionValidationResponse with valid flag and any error details.
    """
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
    else:
        # Unknown language: pass through (will be caught by linters later)
        result = SubmissionValidationResponse(
            valid=True,
            detail=f"No syntax validator for language '{language}'. Passing through.",
        )

    logger.debug(
        f"Validation: lang={language.value} valid={result.valid} "
        f"errors={len(result.errors)}"
    )
    return result
