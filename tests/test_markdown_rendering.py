"""
Tests for markdown rendering functionality.

Run with: uv run pytest tests/test_markdown_rendering.py -v
"""

import pytest
from server.markdown_renderer import render_markdown, render_section_html, render_document_html


class TestBasicMarkdownRendering:
    """Test basic markdown to HTML conversion."""
    
    def test_basic_markdown_to_html(self):
        """Test simple markdown conversion."""
        md = "# Hello World\n\nThis is a **test**."
        html = render_markdown(md)
        
        assert "<h1>Hello World</h1>" in html
        assert "<strong>test</strong>" in html
        assert "<p>" in html
    
    def test_empty_content(self):
        """Test edge case with empty string."""
        html = render_markdown("")
        assert html == ""
    
    def test_headings(self):
        """Test all heading levels."""
        md = """# H1
## H2
### H3
#### H4
##### H5
###### H6"""
        html = render_markdown(md)
        
        assert "<h1>H1</h1>" in html
        assert "<h2>H2</h2>" in html
        assert "<h3>H3</h3>" in html
        assert "<h4>H4</h4>" in html
        assert "<h5>H5</h5>" in html
        assert "<h6>H6</h6>" in html
    
    def test_lists(self):
        """Test ordered and unordered lists."""
        md = """- Item 1
- Item 2
  - Nested item

1. First
2. Second"""
        html = render_markdown(md)
        
        assert "<ul>" in html
        assert "<li>Item 1</li>" in html
        assert "<ol>" in html
        assert "<li>First</li>" in html
    
    def test_special_characters(self):
        """Test HTML escaping of special characters."""
        md = "This has <script>alert('xss')</script> tags"
        html = render_markdown(md)
        
        # Should escape HTML tags
        assert "&lt;script&gt;" in html or "<script>" not in html


class TestCodeBlockHighlighting:
    """Test syntax highlighting for code blocks."""
    
    def test_python_code_block(self):
        """Test Python code block with syntax highlighting."""
        md = """```python
def hello():
    print("Hello, World!")
```"""
        html = render_markdown(md)
        
        # Should contain code highlighting classes
        assert "codehilite" in html
        assert "def" in html
        assert "hello" in html
    
    def test_javascript_code_block(self):
        """Test JavaScript code block."""
        md = """```javascript
function greet() {
    console.log('Hello!');
}
```"""
        html = render_markdown(md)
        
        assert "codehilite" in html
        assert "function" in html
        assert "greet" in html
    
    def test_multiple_code_blocks(self):
        """Test multiple code blocks with different languages."""
        md = """# Code Examples

Python:
```python
x = 42
```

JavaScript:
```javascript
const y = 42;
```"""
        html = render_markdown(md)
        
        # Should have both code blocks
        assert html.count("codehilite") >= 2
        assert "x = 42" in html
        assert "const y = 42" in html
    
    def test_inline_code(self):
        """Test inline code rendering."""
        md = "Use the `print()` function to output text."
        html = render_markdown(md)
        
        assert "<code>print()</code>" in html
    
    def test_code_block_without_language(self):
        """Test code block without language specification."""
        md = """```
plain text code
```"""
        html = render_markdown(md)
        
        assert "plain text code" in html


class TestTablesAndAdvanced:
    """Test tables and advanced markdown features."""
    
    def test_table_rendering(self):
        """Test markdown table conversion."""
        md = """| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |
| Value 3  | Value 4  |"""
        html = render_markdown(md)
        
        assert "<table>" in html
        assert "<th>Column 1</th>" in html
        assert "<td>Value 1</td>" in html
    
    def test_blockquote(self):
        """Test blockquote rendering."""
        md = "> This is a quote"
        html = render_markdown(md)
        
        assert "<blockquote>" in html
        assert "This is a quote" in html
    
    def test_links(self):
        """Test link rendering."""
        md = "[Google](https://google.com)"
        html = render_markdown(md)
        
        assert '<a href="https://google.com">Google</a>' in html


class TestWrapperFunctions:
    """Test wrapper functions for section and document rendering."""
    
    def test_render_section_html(self):
        """Test section rendering wrapper."""
        content = "## Section Title\n\nContent here."
        html = render_section_html(content)
        
        assert "<h2>Section Title</h2>" in html
        assert "Content here" in html
    
    def test_render_document_html(self):
        """Test document rendering wrapper."""
        content = "# Document\n\n## Section 1\n\nText."
        html = render_document_html(content)
        
        assert "<h1>Document</h1>" in html
        assert "<h2>Section 1</h2>" in html


class TestComplexDocument:
    """Test rendering of complex documents with mixed content."""
    
    def test_mixed_content_document(self):
        """Test document with headings, code, lists, and tables."""
        md = """# API Documentation

## Overview

This API provides the following features:

- Authentication
- Data retrieval
- Updates

## Code Example

```python
import requests

response = requests.get('https://api.example.com/data')
print(response.json())
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET    | /api | Get data    |
| POST   | /api | Create data |

> **Note**: All endpoints require authentication.
"""
        html = render_markdown(md)
        
        # Check all elements are present
        assert "<h1>API Documentation</h1>" in html
        assert "<h2>Overview</h2>" in html
        assert "<ul>" in html
        assert "codehilite" in html
        assert "import requests" in html
        assert "<table>" in html
        assert "<blockquote>" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
