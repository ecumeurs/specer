"""
Unit tests for the POST /api/summary endpoint.

These tests mock the Ollama client, so no live server or Ollama instance
is needed. Run with:

    uv run pytest tests/test_summary.py -v
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from server.main import app
from server.document_manager import manager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DOC_NAME = "test_summary_doc"

FEATURE_CONTENT = """### Feature: User Authentication

#### Context, Aim & Integration

This feature provides secure login via OAuth2 and JWT tokens.

#### Constraints

- Minimum 8-character passwords.
- Rate-limit: 5 failed attempts per minute per IP.

#### Technical Requirements

- JWT signed with RS256.
- Refresh tokens stored in an httpOnly cookie.
"""


@pytest.fixture(autouse=True)
def setup_doc():
    """Initialise a test document with a feature section before each test."""
    manager.init_document(DOC_NAME, reset=True)
    manager.save_document_simple(DOC_NAME, FEATURE_CONTENT)
    yield
    # Cleanup: reset the document
    manager.init_document(DOC_NAME, reset=True)


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestGenerateSummaryEndpoint:
    """Tests for POST /api/summary."""

    # -----------------------------------------------------------------------
    # Happy Path
    # -----------------------------------------------------------------------

    def test_happy_path_returns_summary(self, client):
        """
        Main case: a valid feature section + mocked Ollama response.

        Expected: HTTP 200 with {"summary": "<text>"}.
        """
        mock_summary = (
            "The User Authentication feature provides secure login capabilities "
            "using OAuth2 and JWT tokens signed with RS256. It enforces "
            "strict password policies requiring a minimum of eight characters "
            "and protects against brute-force attacks by rate-limiting failed "
            "login attempts to five per minute per IP address. Refresh tokens "
            "are stored in httpOnly cookies to mitigate XSS risks. This feature "
            "integrates with the broader identity management layer and serves as "
            "the foundation for all user-facing access control within the system."
        )

        with patch(
            "server.main.ollama.generate_summary",
            new=AsyncMock(return_value=mock_summary)
        ):
            response = client.post(
                "/api/summary",
                json={"name": DOC_NAME, "section": "Feature: User Authentication"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert data["summary"] == mock_summary

    # -----------------------------------------------------------------------
    # Edge Case 1: Section not found → 404
    # -----------------------------------------------------------------------

    def test_section_not_found_returns_404(self, client):
        """
        Edge case: the requested section title does not exist.

        Expected: HTTP 404 with an informative detail message.
        """
        response = client.post(
            "/api/summary",
            json={"name": DOC_NAME, "section": "Feature: Non-Existent Feature"}
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    # -----------------------------------------------------------------------
    # Edge Case 2: Ollama returns an error string → 500
    # -----------------------------------------------------------------------

    def test_ollama_error_returns_500(self, client):
        """
        Edge case: Ollama returns an error-prefixed string.

        Expected: HTTP 500 with the Ollama error message in the detail.
        """
        with patch(
            "server.main.ollama.generate_summary",
            new=AsyncMock(return_value="Error: Timeout after 60s: TimeoutException")
        ):
            response = client.post(
                "/api/summary",
                json={"name": DOC_NAME, "section": "Feature: User Authentication"}
            )

        assert response.status_code == 500
        data = response.json()
        assert "Error" in data["detail"]
