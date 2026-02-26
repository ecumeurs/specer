from pydantic import BaseModel, Field
from typing import Optional

class BlueprintMeta(BaseModel):
    """
    Metadata for a structural document blueprint.
    Determines how the backend and frontend treat this section type.
    """
    name: str = Field(..., description="Internal name of the blueprint, e.g., 'feature', 'module'")
    type: str = Field(..., description="Type of the blueprint, e.g. 'numerable' (can have many) or 'singleton' (only one)")
    level: int = Field(..., description="The markdown header level of this block (e.g., 3 for ###)")
    allows_summary: bool = Field(default=False, description="Whether this section can generate and hold an AI summary")
    template_prefix: str = Field(..., description="The exact markdown string prefix for titles, e.g., '### Module: ' or '### '")
    parent_section: Optional[str] = Field(default=None, description="The expected parent section title this belongs under. e.g., 'MODULE SPECIFICATIONS (The Children)'")

class Blueprint(BaseModel):
    """
    Represents a full blueprint parsed from a yaml-frontmatter markdown file.
    """
    meta: BlueprintMeta = Field(..., description="The parsed YAML frontmatter")
    template_content: str = Field(..., description="The remaining Markdown template content below the frontmatter")
