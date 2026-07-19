"""
app/utils/code_validator.py — Syntax validation for Python and Java.

Python: uses ast.parse (standard library, zero overhead)
Java:   uses heuristic brace/bracket balance + keyword checks
        (full javac validation requires JDK; we do a lightweight pre-check)
"""

from __future__ import annotations

import ast
import re

from loguru import logger

from app.models.session import Language, SubmissionValidationResponse, ValidationError


# Python Validator
def _validate_python(code: str) -> SubmissionValidationResponse:
    try:
        ast.parse(code)
        return SubmissionValidationResponse(
            valid=True, errors=[], detail="Python syntax is valid."
        )
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


# Java Validator — uses javac for exact line/column error reporting
def _validate_java(code: str) -> SubmissionValidationResponse:
    """
    Validates Java source code by compiling it with javac.
    Returns exact line numbers, column positions, and error messages.
    Falls back to heuristic checks if javac is not available.
    """

    errors: list[ValidationError] = []

    # --- NEW PURE PYTHON APPROACH (javalang) ---
    import javalang  # noqa: PLC0415

    try:
        javalang.parse.parse(code)
        return SubmissionValidationResponse(
            valid=True, errors=[], detail="Java syntax is valid (parsed by javalang)."
        )
    except javalang.parser.JavaSyntaxError as e:
        # e.at.position is a Position object with line and column
        line_no = e.at.position.line if e.at and e.at.position else None
        col_no = e.at.position.column if e.at and e.at.position else None
        errors.append(
            ValidationError(
                field="code",
                message=f"SyntaxError at line {line_no}: {e.description}",
                line=line_no,
                column=col_no,
            )
        )
        # Always run deterministic heuristic checks too so callers can
        # reliably match "class" or "brace" substrings in error messages,
        # even when javalang produced a generic syntax error first.
        heuristic = _validate_java_heuristic(code)
        errors.extend(heuristic.errors)
        return SubmissionValidationResponse(
            valid=False,
            errors=errors,
            detail=f"Java parsing failed with {len(errors)} error(s).",
        )
    except Exception as e:
        logger.error(f"javalang validation error: {e}")
        return _validate_java_heuristic(code)
    # --- END NEW PURE PYTHON APPROACH ---

    """
    # --- PREVIOUS APPROACH (javac subprocess) [COMMENTED OUT FOR TRACKING] ---
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Determine class name from code (javac requires filename == public class name)
            class_match = re.search(r'\bpublic\s+class\s+(\w+)', code)
            class_name = class_match.group(1) if class_match else "Main"
            tmp_file = os.path.join(tmp_dir, f"{class_name}.java")

            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(code)

            result = subprocess.run(
                ["javac", tmp_file],
                capture_output=True,
                text=True,
                timeout=15,   # 15s timeout — plenty for syntax check
            )

            if result.returncode == 0:
                return SubmissionValidationResponse(
                    valid=True,
                    errors=[],
                    detail=f"Java syntax is valid (compiled by javac {_get_javac_version()}).",
                )

            # Parse javac error output:  "FileName.java:10: error: ';' expected"
            stderr = result.stderr
            # Replace the temp file path prefix to keep messages clean
            stderr = stderr.replace(tmp_file + ":", "Line ")

            for line in stderr.splitlines():
                # Match pattern: "Line 5: error: ';' expected"
                m = re.match(r"Line\s+(\d+):\s+(error|warning):\s+(.*)", line)
                if m:
                    lineno, severity, msg = m.group(1), m.group(2), m.group(3)
                    errors.append(ValidationError(
                        field="code",
                        message=f"{severity.capitalize()} at line {lineno}: {msg}",
                        line=int(lineno),
                    ))

            if not errors and stderr.strip():
                # Fallback — javac returned errors but regex didn't parse them
                errors.append(ValidationError(field="code", message=stderr.strip()))

            return SubmissionValidationResponse(
                valid=False,
                errors=errors,
                detail=f"Java compilation failed with {len(errors)} error(s).",
            )

    except FileNotFoundError:
        logger.warning("javac not found — falling back to heuristic Java validation.")
        return _validate_java_heuristic(code)
    except subprocess.TimeoutExpired:
        logger.warning("javac timed out — falling back to heuristic Java validation.")
        return _validate_java_heuristic(code)
    except Exception as e:
        logger.error(f"javac validation error: {e}")
        return _validate_java_heuristic(code)
    # --- END PREVIOUS APPROACH ---
    """


def _get_javac_version() -> str:
    """Return the javac version string for display."""
    import subprocess

    try:
        r = subprocess.run(
            ["javac", "-version"], capture_output=True, text=True, timeout=3
        )
        return (r.stdout or r.stderr).strip()
    except Exception:
        return "unknown"


def _validate_java_heuristic(code: str) -> SubmissionValidationResponse:
    """Lightweight fallback Java validator used when javac is unavailable."""
    errors: list[ValidationError] = []

    if not re.search(r"\b(class|interface|enum)\s+\w+", code):
        errors.append(
            ValidationError(
                field="code",
                message="No class, interface, or enum declaration found. Is this valid Java?",
            )
        )

    open_braces = code.count("{")
    close_braces = code.count("}")
    if open_braces != close_braces:
        errors.append(
            ValidationError(
                field="code",
                message=f"Unbalanced braces: {open_braces} opening '{{' vs {close_braces} closing '}}'.",
            )
        )

    open_parens = code.count("(")
    close_parens = code.count(")")
    if open_parens != close_parens:
        errors.append(
            ValidationError(
                field="code",
                message=f"Unbalanced parentheses: {open_parens} '(' vs {close_parens} ')'.",
            )
        )

    if errors:
        return SubmissionValidationResponse(
            valid=False, errors=errors, detail="Java heuristic pre-validation failed."
        )
    return SubmissionValidationResponse(
        valid=True,
        errors=[],
        detail="Java heuristic pre-check passed (javac unavailable).",
    )


# Public entry point
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
    elif language == Language.unsupported:
        result = SubmissionValidationResponse(
            valid=False,
            errors=[
                ValidationError(
                    field="language",
                    message="Unsupported language detected. Please write code in Java or Python only.",
                )
            ],
            detail="Unsupported Language.",
        )
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
