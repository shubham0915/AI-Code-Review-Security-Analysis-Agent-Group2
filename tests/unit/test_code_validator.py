"""
tests/unit/test_code_validator.py — Unit tests for code validation logic.
"""
import pytest
from app.models.session import Language
from app.utils.code_validator import validate_code


# ─────────────────────────────────────────────────────────────────────────────
# Python validation
# ─────────────────────────────────────────────────────────────────────────────
class TestPythonValidator:

    def test_valid_python_simple(self):
        code = "x = 1 + 2\nprint(x)"
        result = validate_code(code, Language.python)
        assert result.valid is True
        assert result.errors == []

    def test_valid_python_function(self):
        code = """
def greet(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("World"))
"""
        result = validate_code(code, Language.python)
        assert result.valid is True

    def test_invalid_python_syntax(self):
        code = "def broken(\n    pass"
        result = validate_code(code, Language.python)
        assert result.valid is False
        assert len(result.errors) > 0
        assert "SyntaxError" in result.errors[0].message

    def test_invalid_python_indentation(self):
        code = "def foo():\nreturn 1"
        result = validate_code(code, Language.python)
        assert result.valid is False

    def test_empty_code(self):
        result = validate_code("", Language.python)
        assert result.valid is False
        assert "empty" in result.detail.lower()

    def test_whitespace_only(self):
        result = validate_code("   \n\t  ", Language.python)
        assert result.valid is False

    def test_python_with_imports(self):
        code = """
import os
from typing import Optional

def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, default)
"""
        result = validate_code(code, Language.python)
        assert result.valid is True


# ─────────────────────────────────────────────────────────────────────────────
# Java validation
# ─────────────────────────────────────────────────────────────────────────────
class TestJavaValidator:

    def test_valid_java_simple(self):
        code = """
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
"""
        result = validate_code(code, Language.java)
        assert result.valid is True
        assert result.errors == []

    def test_invalid_java_no_class(self):
        code = "System.out.println('Hello');"
        result = validate_code(code, Language.java)
        assert result.valid is False
        assert any("class" in e.message.lower() for e in result.errors)

    def test_invalid_java_unbalanced_braces(self):
        code = """
public class Broken {
    public void method() {
        int x = 1;
    // Missing closing brace for class
"""
        result = validate_code(code, Language.java)
        assert result.valid is False
        assert any("brace" in e.message.lower() for e in result.errors)

    def test_valid_java_with_imports(self):
        code = """
import java.util.List;
import java.util.ArrayList;

public class Example {
    private List<String> items = new ArrayList<>();

    public void addItem(String item) {
        items.add(item);
    }
}
"""
        result = validate_code(code, Language.java)
        assert result.valid is True


# ─────────────────────────────────────────────────────────────────────────────
# Language detection
# ─────────────────────────────────────────────────────────────────────────────
class TestLanguageDetector:

    def test_detect_python_by_extension(self):
        from app.utils.language_detector import detect_language
        lang = detect_language("x = 1", "myfile.py")
        assert lang == Language.python

    def test_detect_java_by_extension(self):
        from app.utils.language_detector import detect_language
        lang = detect_language("public class Foo {}", "Foo.java")
        assert lang == Language.java

    def test_detect_python_by_keywords(self):
        from app.utils.language_detector import detect_language
        code = "def hello():\n    print('Hi')\n    return True"
        lang = detect_language(code, None)
        assert lang == Language.python

    def test_detect_java_by_keywords(self):
        from app.utils.language_detector import detect_language
        code = "public class Test { public static void main(String[] args) {} }"
        lang = detect_language(code, None)
        assert lang == Language.java
