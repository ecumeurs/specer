import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

DATA_DIR = Path("data")
HISTORY_DIR = DATA_DIR / "_history"


class DocumentManager:
    """
    Manages document lifecycle with version control support.
    
    Storage Layout:
        data/
        ├── <name>.md           # Current document content
        ├── <name>_vectors.json # Vector embeddings cache
        ├── <name>_vc.json      # Version control metadata
        └── _history/
            └── <name>/
                ├── v1.md       # Snapshot at version 1
                ├── v2.md       # Snapshot at version 2
                └── ...
    
    Version Control Triggers:
        - Document initialization: version 1
        - All pending merges completed (full validation): version +1
        - Manual edit via direct save: version +1
    """
    
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    def _get_paths(self, name: str):
        """
        Get file paths for a document.
        
        Args:
            name: Document name (will be sanitized)
            
        Returns:
            Tuple of (md_path, vec_path)
        """
        # Sanitize name to prevent path traversal
        safe_name = "".join([c for c in name if c.isalnum() or c in ('-', '_')])
        if not safe_name:
            safe_name = "default"
        
        md_path = DATA_DIR / f"{safe_name}.md"
        vec_path = DATA_DIR / f"{safe_name}_vectors.json"
        return md_path, vec_path
    
    def _get_vc_path(self, name: str) -> Path:
        """Get path to version control metadata file."""
        safe_name = "".join([c for c in name if c.isalnum() or c in ('-', '_')])
        if not safe_name:
            safe_name = "default"
        return DATA_DIR / f"{safe_name}_vc.json"
    
    def _get_history_dir(self, name: str) -> Path:
        """Get path to history directory for a document."""
        safe_name = "".join([c for c in name if c.isalnum() or c in ('-', '_')])
        if not safe_name:
            safe_name = "default"
        return HISTORY_DIR / safe_name

    def init_document(self, name: str, reset: bool = False):
        """
        Initialize a document, optionally resetting to default state.
        
        Creates version 1 with "init" trigger.
        """
        md_path, vec_path = self._get_paths(name)
        vc_path = self._get_vc_path(name)
        
        if reset or not md_path.exists():
            default_content = """# Document Title

## Lexicon

## Context, Aim & Integration

### Context

### Aim

### Integration

## Features

### Feature 1

#### Context, Aim & Integration

#### Constraints

#### User Stories

#### Technical Requirements

#### API

#### Data Layer

#### Validation

#### Dependencies

#### Other Notes

## Roadmap

### Milestone 1

#### Content

#### Validation

"""
            md_path.write_text(default_content, encoding="utf-8")
            vec_path.write_text("[]", encoding="utf-8")
            
            # Initialize version control
            now = datetime.now(timezone.utc).isoformat()
            vc_data = {
                "current_version": 1,
                "created_at": now,
                "versions": [
                    {
                        "version": 1,
                        "timestamp": now,
                        "comment": "Initial document creation",
                        "trigger": "init"
                    }
                ],
                "section_history": {}
            }
            vc_path.write_text(json.dumps(vc_data, indent=2), encoding="utf-8")
            
            # Store initial snapshot
            self._store_snapshot(name, 1, default_content)
            
            return f"Document '{name}' initialized (Reset: {reset})."
        
        return f"Document '{name}' loaded."

    def get_document(self, name: str) -> str:
        """Get the current document content."""
        md_path, _ = self._get_paths(name)
        if not md_path.exists():
            return ""
        return md_path.read_text(encoding="utf-8")

    def save_document(self, name: str, content: str, 
                      trigger: str = "manual_edit",
                      comment: Optional[str] = None,
                      sections_changed: Optional[list] = None):
        """
        Save document and update version control.
        
        Args:
            name: Document name
            content: Full document content
            trigger: What caused this save ("manual_edit", "merge_complete", "section_merge")
            comment: Version comment (auto-generated if None)
            sections_changed: List of section titles that changed
            
        Returns:
            Save confirmation message
        """
        md_path, vec_path = self._get_paths(name)
        
        # Store previous version before overwriting
        if md_path.exists():
            old_content = md_path.read_text(encoding="utf-8")
            if old_content != content:
                self._increment_version(name, trigger, comment, sections_changed)
        
        md_path.write_text(content, encoding="utf-8")
        return "Saved."
    
    def save_document_simple(self, name: str, content: str):
        """
        Save document without version increment (for intermediate states).
        
        Used during merge workflow before full validation.
        """
        md_path, _ = self._get_paths(name)
        md_path.write_text(content, encoding="utf-8")
        return "Saved."

    def get_structure(self, name: str):
        """Parse document into section structure."""
        content = self.get_document(name)
        if not content:
            return []
        
        structure = []
        lines = content.split('\n')
        current_section = {"title": "Introduction", "level": 0, "content": []}
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                # Save previous section
                if current_section["content"]:
                    current_section["content"] = "\n".join(current_section["content"])
                    structure.append(current_section)
                
                # Start new section
                level = len(stripped.split(' ')[0])
                title = stripped.lstrip('#').strip()
                current_section = {"title": title, "level": level, "content": [line]}
            else:
                current_section["content"].append(line)
                
        # Append last section
        if current_section["content"]:
            if isinstance(current_section["content"], list):
                current_section["content"] = "\n".join(current_section["content"])
            structure.append(current_section)
            
        return structure
    
    # -------------------------------------------------------------------------
    # Version Control Methods
    # -------------------------------------------------------------------------
    
    def get_vc_data(self, name: str) -> dict:
        """
        Get version control metadata for a document.
        
        Returns:
            VC data dict or empty structure if not found
        """
        vc_path = self._get_vc_path(name)
        if not vc_path.exists():
            return {
                "current_version": 0,
                "created_at": None,
                "versions": [],
                "section_history": {}
            }
        try:
            return json.loads(vc_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {
                "current_version": 0, 
                "created_at": None,
                "versions": [],
                "section_history": {}
            }
    
    def _save_vc_data(self, name: str, vc_data: dict):
        """Save version control metadata."""
        vc_path = self._get_vc_path(name)
        vc_path.write_text(json.dumps(vc_data, indent=2), encoding="utf-8")
    
    def _store_snapshot(self, name: str, version: int, content: str):
        """
        Store a document snapshot for rollback capability.
        
        Args:
            name: Document name
            version: Version number
            content: Document content at this version
        """
        history_dir = self._get_history_dir(name)
        history_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = history_dir / f"v{version}.md"
        snapshot_path.write_text(content, encoding="utf-8")
    
    def _increment_version(self, name: str, trigger: str, 
                           comment: Optional[str] = None,
                           sections_changed: Optional[list] = None):
        """
        Increment document version with metadata.
        
        Args:
            name: Document name
            trigger: What caused this version bump
            comment: Version comment
            sections_changed: List of changed section titles
        """
        vc_data = self.get_vc_data(name)
        old_version = vc_data.get("current_version", 0)
        new_version = old_version + 1
        
        # Store snapshot of current content before it changes
        current_content = self.get_document(name)
        if current_content:
            self._store_snapshot(name, old_version, current_content)
        
        # Auto-generate comment if not provided
        if not comment:
            if trigger == "merge_complete":
                comment = f"Merged all pending changes"
            elif trigger == "manual_edit":
                comment = f"Manual document edit"
            elif trigger == "section_merge":
                if sections_changed:
                    comment = f"Updated: {', '.join(sections_changed)}"
                else:
                    comment = "Section update"
            else:
                comment = f"{trigger}"
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Add version entry
        version_entry = {
            "version": new_version,
            "timestamp": now,
            "comment": comment,
            "trigger": trigger
        }
        if sections_changed:
            version_entry["sections_changed"] = sections_changed
        
        vc_data["current_version"] = new_version
        vc_data["versions"].append(version_entry)
        
        # Update section history
        if sections_changed:
            for section in sections_changed:
                if section not in vc_data["section_history"]:
                    vc_data["section_history"][section] = []
                vc_data["section_history"][section].append({
                    "version": new_version,
                    "change": comment
                })
        
        self._save_vc_data(name, vc_data)
    
    def complete_merge_validation(self, name: str, comment: Optional[str] = None):
        """
        Called when user validates all merges are complete.
        Triggers version increment with 'merge_complete' trigger.
        
        Args:
            name: Document name
            comment: Optional custom comment
        """
        current_content = self.get_document(name)
        self._increment_version(name, "merge_complete", comment)
        # Store new version snapshot
        vc_data = self.get_vc_data(name)
        self._store_snapshot(name, vc_data["current_version"], current_content)
    
    def rollback_to_version(self, name: str, version: int) -> bool:
        """
        Rollback document to a previous version.
        
        Args:
            name: Document name
            version: Target version number
            
        Returns:
            True if successful, False if version not found
        """
        history_dir = self._get_history_dir(name)
        snapshot_path = history_dir / f"v{version}.md"
        
        if not snapshot_path.exists():
            return False
        
        # Read snapshot content
        content = snapshot_path.read_text(encoding="utf-8")
        
        # Save with rollback trigger (this increments version)
        md_path, _ = self._get_paths(name)
        old_content = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        
        if old_content != content:
            self._increment_version(name, "rollback", f"Rolled back to version {version}")
            md_path.write_text(content, encoding="utf-8")
            
            # Store new snapshot
            vc_data = self.get_vc_data(name)
            self._store_snapshot(name, vc_data["current_version"], content)
        
        return True
    
    def get_document_annotated(self, name: str) -> str:
        """
        Get document with version annotations included.
        
        Injects:
        - Version section at the top (after title)
        - Per-section change history
        
        Returns:
            Annotated document content
        """
        content = self.get_document(name)
        if not content:
            return ""
        
        vc_data = self.get_vc_data(name)
        if not vc_data.get("versions"):
            return content
        
        # Build version summary
        version_section = self._build_version_section(vc_data)
        
        # Insert after title (first # line)
        lines = content.split('\n')
        result_lines = []
        title_found = False
        
        for i, line in enumerate(lines):
            result_lines.append(line)
            
            # Insert version section after the title
            if not title_found and line.strip().startswith('# '):
                title_found = True
                result_lines.append("")
                result_lines.extend(version_section.split('\n'))
        
        # Add section-level annotations
        annotated_content = '\n'.join(result_lines)
        annotated_content = self._add_section_annotations(annotated_content, vc_data)
        
        return annotated_content
    
    def _build_version_section(self, vc_data: dict) -> str:
        """Build the version history section content."""
        lines = [
            "## Version History",
            "",
            f"**Current Version:** {vc_data.get('current_version', 1)}",
            "",
            "| Version | Date | Comment |",
            "|---------|------|---------|"
        ]
        
        for v in vc_data.get("versions", []):
            ts = v.get("timestamp", "")[:10]  # Just date part
            comment = v.get("comment", "")
            lines.append(f"| v{v.get('version')} | {ts} | {comment} |")
        
        lines.append("")
        return '\n'.join(lines)
    
    def _add_section_annotations(self, content: str, vc_data: dict) -> str:
        """Add version annotations to individual sections."""
        section_history = vc_data.get("section_history", {})
        if not section_history:
            return content
        
        lines = content.split('\n')
        result_lines = []
        
        for line in lines:
            result_lines.append(line)
            
            # Check if this is a section header that has history
            if line.strip().startswith('#'):
                title = line.strip().lstrip('#').strip()
                
                # Check for matching history (partial match)
                for section_name, history in section_history.items():
                    if section_name.lower() in title.lower() or title.lower() in section_name.lower():
                        # Add annotation
                        if history:
                            latest = history[-1]
                            result_lines.append(f"> *v{latest['version']}: {latest['change']}*")
                        break
        
        return '\n'.join(result_lines)
    
    def list_versions(self, name: str) -> list:
        """
        List all versions for a document.
        
        Returns:
            List of version metadata dicts
        """
        vc_data = self.get_vc_data(name)
        return vc_data.get("versions", [])


manager = DocumentManager()

