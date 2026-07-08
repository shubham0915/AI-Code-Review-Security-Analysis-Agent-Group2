"""
tests/integration/test_submit_api.py — Integration tests for the Code Submission API.

Requires: FastAPI TestClient (no live Redis needed — Redis calls are mocked).
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

# Patch Redis before importing app
with patch("app.cache.redis_cache.get_redis_client") as mock_redis_factory:
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis_factory.return_value = mock_redis

    from app.main import app

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────
class TestHealthEndpoints:

    def test_liveness(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Submit paste
# ─────────────────────────────────────────────────────────────────────────────
class TestSubmitPaste:

    VALID_PYTHON = "def add(a, b):\n    return a + b\n"
    VALID_JAVA = """
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
}
"""

    @patch("app.cache.redis_cache.get_redis_client")
    def test_submit_valid_python(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        mock_r.setex = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_r

        payload = {"code": self.VALID_PYTHON, "language": "python"}
        resp = client.post("/api/v1/submit/paste", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert "session_id" in data
        assert data["status"] == "queued"
        assert data["language"] == "python"
        assert data["lines_of_code"] > 0

    @patch("app.cache.redis_cache.get_redis_client")
    def test_submit_valid_java(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        mock_r.setex = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_r

        payload = {"code": self.VALID_JAVA, "language": "java"}
        resp = client.post("/api/v1/submit/paste", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["language"] == "java"

    @patch("app.cache.redis_cache.get_redis_client")
    def test_submit_auto_detects_python(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        mock_r.setex = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_r

        payload = {"code": "def hello():\n    print('hi')", "language": "auto"}
        resp = client.post("/api/v1/submit/paste", json=payload)
        assert resp.status_code == 202
        assert resp.json()["language"] == "python"

    def test_submit_invalid_python_syntax(self):
        payload = {"code": "def broken(\n    pass", "language": "python"}
        resp = client.post("/api/v1/submit/paste", json=payload)
        assert resp.status_code == 422

    def test_submit_empty_code(self):
        payload = {"code": "", "language": "python"}
        resp = client.post("/api/v1/submit/paste", json=payload)
        # Pydantic min_length=1 constraint
        assert resp.status_code == 422

    def test_submit_too_many_lines(self):
        big_code = "\n".join(["x = 1"] * 11000)
        payload = {"code": big_code, "language": "python"}
        resp = client.post("/api/v1/submit/paste", json=payload)
        assert resp.status_code == 413


# ─────────────────────────────────────────────────────────────────────────────
# Validate endpoint
# ─────────────────────────────────────────────────────────────────────────────
class TestValidateEndpoint:

    def test_validate_valid_python(self):
        payload = {"code": "x = 1 + 2\nprint(x)", "language": "python"}
        resp = client.post("/api/v1/submit/validate", json=payload)
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_invalid_python(self):
        payload = {"code": "def bad(\n  return 1", "language": "python"}
        resp = client.post("/api/v1/submit/validate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_validate_valid_java(self):
        code = "public class Foo { public void bar() {} }"
        payload = {"code": code, "language": "java"}
        resp = client.post("/api/v1/submit/validate", json=payload)
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


# ─────────────────────────────────────────────────────────────────────────────
# File upload
# ─────────────────────────────────────────────────────────────────────────────
class TestFileUpload:

    @patch("app.cache.redis_cache.get_redis_client")
    def test_upload_python_file(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        mock_r.setex = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_r

        code = b"def add(a, b):\n    return a + b\n"
        resp = client.post(
            "/api/v1/submit/file",
            files={"file": ("test.py", code, "text/plain")},
            data={"language": "python"},
        )
        assert resp.status_code == 202
        assert resp.json()["language"] == "python"

    def test_upload_unsupported_extension(self):
        resp = client.post(
            "/api/v1/submit/file",
            files={"file": ("test.cpp", b"int main() {}", "text/plain")},
            data={"language": "auto"},
        )
        assert resp.status_code == 415
