"""
Markdown to HTML rendering with syntax highlighting.

This module provides utilities to convert markdown content to HTML
with proper code block syntax highlighting using Pygments.
"""

import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension


def render_markdown(content: str) -> str:
    """
    Convert markdown content to HTML with syntax highlighting.
    
    Args:
        content: Markdown text to convert
        
    Returns:
        HTML string with syntax-highlighted code blocks
        
    Example:
        >>> md = "# Hello\\n\\n```python\\nprint('hi')\\n```"
        >>> html = render_markdown(md)
        >>> "<h1>Hello</h1>" in html
        True
    """
    if not content:
        return ""
    
    # Configure markdown extensions
    extensions = [
        # Code highlighting with Pygments
        CodeHiliteExtension(
            css_class='codehilite',
            linenums=False,
            guess_lang=True
        ),
        # Fenced code blocks (```)
        FencedCodeExtension(),
        # Table support
        TableExtension(),
    ]
    
    # Convert markdown to HTML
    md = markdown.Markdown(extensions=extensions)
    html = md.convert(content)
    
    return html


def render_section_html(section_content: str) -> str:
    """
    Render a document section as HTML.
    
    Wrapper around render_markdown for section-specific rendering.
    
    Args:
        section_content: Section markdown content
        
    Returns:
        HTML string
    """
    return render_markdown(section_content)


def render_document_html(document_content: str) -> str:
    """
    Render a full document as HTML.
    
    Wrapper around render_markdown for document-level rendering.
    
    Args:
        document_content: Full document markdown content
        
    Returns:
        HTML string
    """
    return render_markdown(document_content)
