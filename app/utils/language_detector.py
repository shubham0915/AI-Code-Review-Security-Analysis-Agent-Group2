"""
app/utils/language_detector.py — Detect Python vs Java from code and filename.

Strategy (in order of priority):
  1. File extension (.py → python, .java → java)
  2. Pygments lexer guess
  3. Heuristic keyword scan (Java-biased on ties — Java keywords are more specific)
  4. Default: python
"""
from __future__ import annotations

import os
from typing import Optional

from loguru import logger

from app.models.session import Language


# Java-specific keywords — these are VERY unlikely to appear in Python code
_JAVA_KEYWORDS = frozenset([
    "public class", "private class", "protected class",
    "public static void main", "import java.", "import javax.",
    "System.out.", "System.err.", "System.in.",
    "extends ", "implements ", "new ArrayList", "new HashMap",
    "new LinkedList", "new HashSet",
    "@Override", "@NotNull", "@Nullable",
    "throws ", "catch (", "finally {",
    "String[] args", "void main", "public static",
    "private static", "protected static",
])

# Python-specific patterns — deliberately avoiding 'import ' (too generic)
_PYTHON_KEYWORDS = frozenset([
    "def ",           # Python function definitions
    "elif ",          # Python-specific (Java uses 'else if')
    "__init__",       # Python class constructor magic method
    "self.",          # Python instance method first argument
    "lambda ",        # Python anonymous functions
    "yield ",         # Python generators
    "if __name__",    # Python main guard
    "#!/usr/bin/env python",   # Python shebang
    "# -*-",          # Python encoding declaration
    "print(",         # Python 3 print function (careful — not definitive alone)
    "from __future__",        # Python future imports
])


def detect_language(code: str, filename: Optional[str] = None) -> Language:
    """
    Return Language.python or Language.java.
    Never returns Language.auto.
    """
    # 1. Extension hint — most reliable signal
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".py":
            return Language.python
        if ext == ".java":
            return Language.java
        if ext in [".js", ".ts", ".html", ".css", ".cpp", ".c", ".go", ".rs", ".rb", ".php", ".sh", ".json"]:
            logger.warning(f"Unsupported file extension detected: {ext}")
            return Language.unsupported

    # --- NEW ML-BASED APPROACH (Google Magika) ---
    try:
        from magika import Magika
        m = Magika()
        res = m.identify_bytes(code.encode("utf-8", errors="replace"))
        label = res.output.label.lower()
        
        logger.debug(f"Magika ML detected label: {label} (score: {res.output.score})")
        
        if label == "python":
            return Language.python
        if label == "java":
            return Language.java
        
        # Magika sometimes classifies tiny snippets as 'txt' or 'empty'
        # If it's highly confident it's something else (like 'javascript', 'html'), we reject it.
        if label not in ["txt", "empty", "unknown", "python", "java"]:
            logger.warning(f"Magika ML rejected unsupported language: {label}")
            return Language.unsupported
            
    except Exception as e:
        logger.error(f"Magika detection error: {e}")
        
    # --- END NEW ML-BASED APPROACH ---

    """
    # --- PREVIOUS APPROACH (Pygments + Keyword Heuristics) [COMMENTED OUT FOR TRACKING] ---
    # 2. Try pygments (the same engine VS Code uses)
    try:
        from pygments.lexers import guess_lexer
        from pygments.lexers import PythonLexer, JavaLexer

        lexer = guess_lexer(code)
        
        # Check explicit hits
        if isinstance(lexer, PythonLexer):
            return Language.python
        if isinstance(lexer, JavaLexer):
            return Language.java
            
        # If Pygments explicitly identifies it as a known but unsupported language
        # (ignoring 'Text only' since it's a fallback for small snippets)
        name = lexer.name.lower()
        if name not in ["text only", "text", "python", "java"]:
            logger.warning(f"Pygments detected unsupported language: {lexer.name}")
            return Language.unsupported
    except Exception:
        pass

    # 3. Heuristic keyword scan
    sample = code[:3000]   # Only check first 3000 chars
    java_score = sum(1 for kw in _JAVA_KEYWORDS if kw in sample)
    python_score = sum(1 for kw in _PYTHON_KEYWORDS if kw in sample)

    logger.debug(f"Language scores — Java: {java_score}, Python: {python_score}")

    # Java keywords are highly specific (e.g. 'import java.', 'System.out.'),
    # so we favour Java on ties (java_score >= python_score AND java_score > 0)
    if java_score > 0 and java_score >= python_score:
        logger.debug(f"Language detected: java (score: java={java_score}, python={python_score})")
        return Language.java
    if python_score > 0:
        logger.debug(f"Language detected: python (score: python={python_score}, java={java_score})")
        return Language.python

    # 4. Default: if no keywords match and Pygments didn't catch it, it's likely unsupported text/code
    logger.warning("Could not detect any Python or Java patterns; marking as unsupported.")
    return Language.unsupported
    # --- END PREVIOUS APPROACH ---
    """
    
    # Fallback for ML approach if Magika returns 'txt'
    # We use a very fast naive check here just in case Magika missed a tiny snippet
    if "public class" in code or "System.out" in code or "import java." in code:
        return Language.java
    if "def " in code or "import " in code or "print(" in code:
        return Language.python
        
    return Language.unsupported
