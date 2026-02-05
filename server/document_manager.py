import os
import json
from pathlib import Path

DATA_DIR = Path("data")

class DocumentManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _get_paths(self, name: str):
        # Sanitize name to prevent path traversal
        safe_name = "".join([c for c in name if c.isalnum() or c in ('-', '_')])
        if not safe_name:
            safe_name = "default"
        
        md_path = DATA_DIR / f"{safe_name}.md"
        vec_path = DATA_DIR / f"{safe_name}_vectors.json"
        return md_path, vec_path

    def init_document(self, name: str, reset: bool = False):
        md_path, vec_path = self._get_paths(name)
        
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
            return f"Document '{name}' initialized (Reset: {reset})."
        
        return f"Document '{name}' loaded."

    def get_document(self, name: str) -> str:
        md_path, _ = self._get_paths(name)
        if not md_path.exists():
            return ""
        return md_path.read_text(encoding="utf-8")

    def save_document(self, name: str, content: str):
        md_path, vec_path = self._get_paths(name)
        md_path.write_text(content, encoding="utf-8")
        # In a real scenario, we would invalidate vectors here
        # For now, we leave the vector file as is (or reset it if logic dictates)
        return "Saved."

    def get_structure(self, name: str):
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
                current_section = {"title": title, "level": level, "content": [line]} # Include header in content
            else:
                current_section["content"].append(line)
                
        # Append last section
        if current_section["content"]:
            if isinstance(current_section["content"], list):
                current_section["content"] = "\n".join(current_section["content"])
            structure.append(current_section)
            
        return structure

manager = DocumentManager()
