import sys
from pathlib import Path
from unittest.mock import patch

# pyrefly: ignore [missing-import]
from streamlit.testing.v1 import AppTest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))


def test_streamlit_app_loads_and_local_mode_active():
    """
    Test that the Streamlit app initializes successfully.
    We patch the API health check to return False, forcing 'local' mode.
    """
    app_path = PROJECT_ROOT / "frontend" / "app.py"

    # Run the Streamlit app using AppTest
    at = AppTest.from_file(str(app_path))

    # Patch the check_api function so we don't depend on the backend running during the unit test
    with patch("frontend.app.check_api", return_value=False):
        at.run()

    # 1. Check that the app ran without throwing exceptions
    assert not at.exception, (
        f"App raised an exception: {at.exception[0].message if at.exception else ''}"
    )

    # 2. Check session state initialization
    # 3. Check that api_mode is correctly set (will be 'api' if backend is running, 'local' otherwise)
    assert at.session_state["api_mode"] in ["api", "local"]

    # 4. Check for key UI elements
    # The first selectbox should be the Language selector
    assert len(at.selectbox) > 0
    language_selector = at.selectbox[0]
    assert language_selector.label == "Language"
    assert "auto" in language_selector.options


def test_local_validation_function():
    """Test the browser-local code validation function inside the frontend."""
    # We can import functions directly from the app
    from frontend.app import _local_validate

    # Test valid python
    valid_py = "def hello():\n    print('world')"
    res = _local_validate(valid_py, "python")
    assert res["valid"] is True

    # Test invalid python
    invalid_py = "def hello()\n    print('world')"  # missing colon
    res = _local_validate(invalid_py, "python")
    assert res["valid"] is False
    assert "SyntaxError" in res["errors"][0]["message"]

    # Test valid java (approximate, needs class keyword)
    valid_java = "public class Main { public static void main(String[] args) {} }"
    res = _local_validate(valid_java, "java")
    assert res["valid"] is True

    # Test invalid java (missing closing brace)
    invalid_java = "public class Main { public static void main(String[] args) {"
    res = _local_validate(invalid_java, "java")
    assert res["valid"] is False
    # Depending on how it evaluates, unbalanced braces might be the first or second error.
    error_messages = [e["message"] for e in res["errors"]]
    assert any("Unbalanced braces" in msg for msg in error_messages)
