"""
app/utils/language_detector.py — Detect Python vs Java from code and filename.

Strategy (in order of priority):
  1. File extension (.py → python, .java → java)
  2. Pygments lexer guess
  3. Heuristic keyword scan
  4. Default: python
"""
from __future__ import annotations

import os
from typing import Optional

from loguru import logger

from app.models.session import Language


# Java-specific keywords that rarely appear in Python
_JAVA_KEYWORDS = frozenset([
    "public class", "private class", "protected class",
    "public static void main", "import java.", "System.out.",
    "extends ", "implements ", "new ArrayList", "new HashMap",
    "@Override", "throws ", "catch (", "finally {",
])

# Python-specific patterns
_PYTHON_KEYWORDS = frozenset([
    "def ", "import ", "from ", "elif ", "print(",
    "__init__", "self.", "lambda ", "yield ",
    "if __name__", "#!/usr/bin/env python",
])


def detect_language(code: str, filename: Optional[str] = None) -> Language:
    """
    Return Language.python or Language.java.
    Never returns Language.auto.
    """
    # 1. Extension hint
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".py":
            return Language.python
        if ext == ".java":
            return Language.java

    # 2. Try pygments
    try:
        from pygments.lexers import guess_lexer
        from pygments.lexers import PythonLexer, JavaLexer

        lexer = guess_lexer(code)
        if isinstance(lexer, PythonLexer):
            return Language.python
        if isinstance(lexer, JavaLexer):
            return Language.java
    except Exception:
        pass

    # 3. Heuristic keyword scan
    sample = code[:3000]   # Only check first 3000 chars
    java_score = sum(1 for kw in _JAVA_KEYWORDS if kw in sample)
    python_score = sum(1 for kw in _PYTHON_KEYWORDS if kw in sample)

    if java_score > python_score:
        logger.debug(f"Language detected: java (score: java={java_score}, python={python_score})")
        return Language.java
    if python_score > 0:
        logger.debug(f"Language detected: python (score: python={python_score}, java={java_score})")
        return Language.python

    # 4. Default
    logger.warning("Could not detect language; defaulting to Python")
    return Language.python
