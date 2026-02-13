"""
API integration tests for render endpoints.

Requires running server: docker compose up -d
Run with: uv run pytest tests/test_render_api.py -v
"""

import pytest
import httpx

BASE_URL = "http://localhost:8001/api"
TEST_DOC = "test_render_doc"


@pytest.fixture(scope="module")
def client():
    """Create HTTP client for testing."""
    return httpx.Client(timeout=30.0)


@pytest.fixture(scope="module")
def setup_test_document(client):
    """Setup a test document with code blocks."""
    # Initialize document
    client.post(
        f"{BASE_URL}/init",
        json={"name": TEST_DOC, "reset": True}
    )
    
    # Add content with code blocks
    content = """# Test Document

## Features

### Feature: Code Examples

This section contains code examples.

#### Python Example

```python
def calculate_sum(a, b):
    return a + b

result = calculate_sum(5, 3)
print(f"Result: {result}")
```

#### JavaScript Example

```javascript
function greet(name) {
    return `Hello, ${name}!`;
}

console.log(greet('World'));
```

## Data

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
"""
    
    client.post(
        f"{BASE_URL}/commit",
        json={"name": TEST_DOC, "content": content}
    )
    
    yield
    
    # Cleanup is optional since it's a test document


class TestRenderSectionEndpoint:
    """Test /api/render/section endpoint."""
    
    def test_render_section_markdown(self, client, setup_test_document):
        """Test rendering section in markdown format."""
        response = client.get(
            f"{BASE_URL}/render/section/{TEST_DOC}/Feature: Code Examples",
            params={"format": "markdown"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["format"] == "markdown"
        assert "```python" in data["content"]
        assert "def calculate_sum" in data["content"]
    
    def test_render_section_html(self, client, setup_test_document):
        """Test rendering section in HTML format."""
        response = client.get(
            f"{BASE_URL}/render/section/{TEST_DOC}/Feature: Code Examples",
            params={"format": "html"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["format"] == "html"
        # Should have HTML tags
        assert "<h" in data["content"]  # Some heading tag
        # Should have code highlighting
        assert "codehilite" in data["content"]
        assert "def calculate_sum" in data["content"]
    
    def test_render_section_default_format(self, client, setup_test_document):
        """Test that default format is markdown."""
        response = client.get(
            f"{BASE_URL}/render/section/{TEST_DOC}/Features"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["format"] == "markdown"
    
    def test_nonexistent_section(self, client, setup_test_document):
        """Test error handling for missing section."""
        response = client.get(
            f"{BASE_URL}/render/section/{TEST_DOC}/Nonexistent Section"
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestRenderDocumentEndpoint:
    """Test /api/render/document endpoint."""
    
    def test_render_document_markdown(self, client, setup_test_document):
        """Test rendering full document in markdown."""
        response = client.get(
            f"{BASE_URL}/render/document/{TEST_DOC}",
            params={"format": "markdown"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["format"] == "markdown"
        assert "# Test Document" in data["content"]
        assert "```python" in data["content"]
        assert "```javascript" in data["content"]
    
    def test_render_document_html(self, client, setup_test_document):
        """Test rendering full document in HTML."""
        response = client.get(
            f"{BASE_URL}/render/document/{TEST_DOC}",
            params={"format": "html"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["format"] == "html"
        # Should have HTML structure
        assert "<h1>Test Document</h1>" in data["content"]
        assert "<h2>Features</h2>" in data["content"]
        # Should have code highlighting
        assert "codehilite" in data["content"]
        # Should have table
        assert "<table>" in data["content"]
    
    def test_render_document_default_format(self, client, setup_test_document):
        """Test that default format is markdown."""
        response = client.get(
            f"{BASE_URL}/render/document/{TEST_DOC}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["format"] == "markdown"
    
    def test_nonexistent_document(self, client):
        """Test error handling for missing document."""
        response = client.get(
            f"{BASE_URL}/render/document/nonexistent_doc_12345"
        )
        
        assert response.status_code == 404


class TestCodeHighlightingInRendering:
    """Test that code blocks are properly highlighted in HTML output."""
    
    def test_python_syntax_highlighting(self, client, setup_test_document):
        """Test Python code is highlighted."""
        response = client.get(
            f"{BASE_URL}/render/section/{TEST_DOC}/Feature: Code Examples",
            params={"format": "html"}
        )
        
        html = response.json()["content"]
        
        # Should have highlighting wrapper
        assert "codehilite" in html
        # Should contain the Python code
        assert "calculate_sum" in html
        assert "print" in html
    
    def test_javascript_syntax_highlighting(self, client, setup_test_document):
        """Test JavaScript code is highlighted."""
        response = client.get(
            f"{BASE_URL}/render/document/{TEST_DOC}",
            params={"format": "html"}
        )
        
        html = response.json()["content"]
        
        # Should have highlighting
        assert "codehilite" in html
        # Should contain JavaScript code
        assert "function greet" in html
        assert "console.log" in html


class TestTableRendering:
    """Test that markdown tables are properly rendered."""
    
    def test_table_in_html(self, client, setup_test_document):
        """Test table rendering in HTML."""
        response = client.get(
            f"{BASE_URL}/render/document/{TEST_DOC}",
            params={"format": "html"}
        )
        
        html = response.json()["content"]
        
        assert "<table>" in html
        assert "<th>Column 1</th>" in html
        assert "<td>Data 1</td>" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
